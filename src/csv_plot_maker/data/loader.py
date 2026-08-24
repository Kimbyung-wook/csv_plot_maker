from __future__ import annotations

import time

import numpy as np
import polars as pl

from csv_plot_maker.data.column_store import ColumnStore


def peek_schema(path: str) -> list[str]:
    """Return column names near-instantly, without parsing the full file."""
    schema = pl.scan_csv(path).collect_schema()
    return ["Sequential"] + list(schema.names())


def load_csv(path: str) -> ColumnStore:
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
    """
    start = time.perf_counter()
    try:
        df = pl.read_csv(path, try_parse_dates=True)
    except pl.exceptions.PolarsError:
        try:
            df = pl.read_csv(path, try_parse_dates=True, infer_schema_length=None)
        except pl.exceptions.PolarsError:
            df = pl.read_csv(
                path, try_parse_dates=True, infer_schema_length=None, ignore_errors=True
            )
    store = ColumnStore(source_path=path, row_count=df.height)

    store.columns["Sequential"] = np.arange(1, df.height + 1, dtype=np.float64)
    store.dtypes["Sequential"] = "Int64"
    store.numeric["Sequential"] = True

    for name, dtype in zip(df.columns, df.dtypes):
        is_numeric = dtype.is_numeric()
        is_temporal = dtype in (pl.Date, pl.Datetime)
        store.dtypes[name] = str(dtype)
        store.numeric[name] = is_numeric or is_temporal

        if not (is_numeric or is_temporal):
            # Non-numeric columns can never be plotted -- every column-
            # selection path in the UI gates on ColumnStore.numeric_column_
            # names(), which this dtype flag alone already satisfies. Convert
            # nothing for them: a numpy object-array of Python str objects is
            # typically far larger in memory than the column's raw CSV bytes,
            # so materializing it would be pure waste for data that's never
            # actually used. drop_in_place (instead of just leaving it in df)
            # also releases polars' own memory for it immediately rather than
            # holding it for the rest of this loop.
            df.drop_in_place(name)
            continue

        # drop_in_place both extracts the column and removes it from df, so
        # df's own memory shrinks column-by-column as the loop progresses
        # instead of staying at its full post-read size for the whole loop
        # (which would otherwise mean the full DataFrame and the growing
        # numpy dict are both fully resident in memory at the same time).
        column = df.drop_in_place(name)
        if is_numeric:
            store.columns[name] = column.to_numpy()
        else:
            # Physical (integer) representation converts cleanly to a plottable numeric axis.
            store.columns[name] = column.to_physical().to_numpy().astype(np.float64)

    store.load_time_ms = (time.perf_counter() - start) * 1000
    return store
