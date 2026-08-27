from __future__ import annotations

import time

import numpy as np
import polars as pl

from csv_plot_maker.data.column_store import ColumnStore
from csv_plot_maker.data.header_trim import trim_headers

# Round-trip tolerance for deciding whether a float64 column can be stored as
# float32 (halving its memory footprint) without a plot-visible precision
# loss. Ordinary sensor-style decimal values (rtol looser than float32's own
# ~1.19e-7 machine epsilon, so smoothly-varying readings always pass) are
# fine to downcast; atol guards near-zero values.
_FLOAT32_DOWNCAST_RTOL = 1e-6
_FLOAT32_DOWNCAST_ATOL = 1e-9

# float32 can only represent integers exactly up to 2**24 (16,777,216) --
# beyond that, distinct large values (e.g. a big counter or a raw timestamp
# stored as a float column) can collapse onto the same float32 value even
# though the *relative* rounding error stays tiny. Magnitude check first, so
# these columns are rejected outright regardless of the round-trip result.
_FLOAT32_SAFE_MAGNITUDE = 2**24


def _downcast_to_float32_if_safe(arr: np.ndarray) -> np.ndarray:
    """Return `arr` as float32 if that's safe (bounded magnitude + round-trips within tolerance), else float64 unchanged."""
    finite = arr[np.isfinite(arr)]
    if finite.size and np.max(np.abs(finite)) >= _FLOAT32_SAFE_MAGNITUDE:
        return arr
    candidate = arr.astype(np.float32)
    if np.allclose(arr, candidate, rtol=_FLOAT32_DOWNCAST_RTOL, atol=_FLOAT32_DOWNCAST_ATOL, equal_nan=True):
        return candidate
    return arr


# polars' CSV schema inference always widens whole-number columns to Int64
# regardless of their actual value range (a column of 0/1 flags gets the same
# 8 bytes/value as a column of huge counters), so this is worth narrowing
# unconditionally -- unlike the float32 case there's no precision trade-off,
# just picking the smallest dtype that can hold the column's real min/max.
_INT_WIDTHS = (np.int8, np.int16, np.int32, np.int64)


def _narrow_integer_width(arr: np.ndarray) -> np.ndarray:
    """Return `arr` cast down to the smallest signed integer dtype that fits its actual min/max."""
    if arr.size == 0:
        return arr
    lo, hi = int(arr.min()), int(arr.max())
    for dtype in _INT_WIDTHS:
        info = np.iinfo(dtype)
        if info.min <= lo and hi <= info.max:
            return arr.astype(dtype) if arr.dtype != dtype else arr
    return arr


def peek_schema(path: str, header_trim_keywords: list[str] | None = None) -> list[str]:
    """Return column names near-instantly, without parsing the full file."""
    schema = pl.scan_csv(path).collect_schema()
    names = list(schema.names())
    if header_trim_keywords:
        names = trim_headers(names, header_trim_keywords)
    return ["Sequential"] + names


def load_csv(path: str, header_trim_keywords: list[str] | None = None) -> ColumnStore:
    """Fully parse a CSV (multithreaded) and convert columns to numpy arrays.

    Runs on a worker thread (see utils.workers.CallableWorker) so the UI
    never blocks on multi-million-row files.

    A synthetic "Sequential" column (1..row_count) is added ahead of every
    real column so there's always a reliable, monotonic fallback X axis if
    the file's own timestamp column turns out to be missing or malformed.

    Schema inference uses a three-step fallback, fastest first:
      1. polars' default sampled inference (fast -- reads a leading chunk of
         rows to guess each column's dtype, then parses the rest against it).
         This is fine for the vast majority of well-behaved CSVs.
      2. infer_schema_length=None, which inspects every row before parsing.
         Some field logs mix an integer-looking prefix with float values
         further down a column (e.g. "16.316801" appearing after thousands
         of rows that looked like plain ints); the sampled pass in step 1
         locks in "int" and hard-fails the moment it hits that float, so we
         only pay the cost of a full-file inference pass when step 1 fails.
      3. ignore_errors=True on top of the full inference, so a column that
         still can't be parsed cleanly (genuinely malformed data) turns bad
         cells into null instead of aborting the entire load.

    Retries only happen on `pl.exceptions.PolarsError` (schema/parsing
    failures) -- not on `MemoryError` or anything else unexpected, so a load
    that's already run out of memory on the fast path doesn't get retried
    with two more, progressively more expensive full-file re-parses.

    n_threads=1: polars' default (one worker per CPU core) splits very wide
    files into hundreds of small chunks per column during parsing, and that
    fragmentation isn't released even after the load finishes (rechunk=True
    doesn't help either -- measured on a 1003-column fixture: peak RSS was
    ~10x the file's on-disk size with default threading vs ~6x pinned to a
    single thread, with no measurable load-time cost on the files tested).
    """
    start = time.perf_counter()
    try:
        df = pl.read_csv(path, try_parse_dates=True, n_threads=1)
    except pl.exceptions.PolarsError:
        try:
            df = pl.read_csv(path, try_parse_dates=True, infer_schema_length=None, n_threads=1)
        except pl.exceptions.PolarsError:
            df = pl.read_csv(
                path,
                try_parse_dates=True,
                infer_schema_length=None,
                ignore_errors=True,
                n_threads=1,
            )
    if header_trim_keywords:
        df.columns = trim_headers(df.columns, header_trim_keywords)
    store = ColumnStore(source_path=path, row_count=df.height)

    store.columns["Sequential"] = np.arange(1, df.height + 1, dtype=np.float64)
    store.dtypes["Sequential"] = "Int64"
    store.numeric["Sequential"] = True

    for name, dtype in zip(df.columns, df.dtypes):
        is_numeric = dtype.is_numeric()
        is_temporal = dtype in (pl.Date, pl.Datetime, pl.Time)
        store.dtypes[name] = str(dtype)
        store.numeric[name] = is_numeric or is_temporal

        if not (is_numeric or is_temporal):
            column = df.drop_in_place(name)
            if dtype == pl.String:
                if column.null_count() == df.height:
                    # A column whose trailing field is omitted on every
                    # single row (ragged CSV rows -- no data past this point
                    # rather than an explicit empty field) can't have its
                    # dtype inferred at all and comes back as String,
                    # all-null. It's still meant to be a numeric column, just
                    # entirely empty in this file, so keep it plottable
                    # (all-NaN) instead of dropping it like a genuine
                    # non-numeric column (e.g. a text "label" column).
                    store.numeric[name] = True
                    store.columns[name] = np.full(df.height, np.nan, dtype=np.float64)
                    continue
                # A column can also land on String while genuinely holding
                # numeric text: if this column is null across almost the
                # entire sampled inference window (e.g. a rarely-updated
                # periodic "echo" field), polars can't guess a numeric dtype
                # from nothing and defaults the column to String -- then
                # happily parses the real numbers that do show up later in
                # the file as their string form, without ever raising the
                # schema error the retry ladder above is watching for. Try to
                # recover the real dtype now that every value is in hand:
                # a strict cast succeeds only if every non-null value
                # actually parses as that type, so a genuine text column
                # (e.g. "label") correctly fails both and falls through to
                # being dropped below.
                for numeric_dtype in (pl.Int64, pl.Float64):
                    try:
                        numeric_column = column.cast(numeric_dtype, strict=True)
                    except pl.exceptions.PolarsError:
                        continue
                    store.numeric[name] = True
                    arr = numeric_column.to_numpy()
                    if arr.dtype == np.float64:
                        arr = _downcast_to_float32_if_safe(arr)
                    elif np.issubdtype(arr.dtype, np.integer):
                        arr = _narrow_integer_width(arr)
                    store.columns[name] = arr
                    break
            # Non-numeric columns can never be plotted -- every column-
            # selection path in the UI gates on ColumnStore.numeric_column_
            # names(), which this dtype flag alone already satisfies. Convert
            # nothing for them: a numpy object-array of Python str objects is
            # typically far larger in memory than the column's raw CSV bytes,
            # so materializing it would be pure waste for data that's never
            # actually used.
            continue

        # drop_in_place both extracts the column and removes it from df, so
        # df's own memory shrinks column-by-column as the loop progresses
        # instead of staying at its full post-read size for the whole loop
        # (which would otherwise mean the full DataFrame and the growing
        # numpy dict are both fully resident in memory at the same time).
        column = df.drop_in_place(name)
        if is_numeric:
            arr = column.to_numpy()
            # Branch on the array's actual resulting dtype rather than the
            # source polars dtype: a nullable Int64 column comes back from
            # to_numpy() as float64 (nulls become NaN), and that column
            # needs the float32 downcast path, not the integer one.
            if arr.dtype == np.float64:
                arr = _downcast_to_float32_if_safe(arr)
            elif np.issubdtype(arr.dtype, np.integer):
                arr = _narrow_integer_width(arr)
            store.columns[name] = arr
        else:
            # Physical representation converts cleanly to a plottable numeric
            # axis. pl.Time's physical value is nanoseconds since midnight --
            # divide down to seconds, the unit users actually want to plot
            # against; Date/Datetime keep their raw physical value (days /
            # microseconds since epoch) since nothing has asked for those in
            # a different unit yet.
            physical = column.to_physical().to_numpy().astype(np.float64)
            store.columns[name] = physical / 1e9 if dtype == pl.Time else physical

    del df
    store.load_time_ms = (time.perf_counter() - start) * 1000
    return store
