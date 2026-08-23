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
    """
    start = time.perf_counter()
    try:
        df = pl.read_csv(path, try_parse_dates=True)
    except Exception:
        try:
            df = pl.read_csv(path, try_parse_dates=True, infer_schema_length=None)
        except Exception:
            df = pl.read_csv(
                path, try_parse_dates=True, infer_schema_length=None, ignore_errors=True
            )
    store = ColumnStore(source_path=path, row_count=df.height)

    store.columns["Sequential"] = np.arange(1, df.height + 1, dtype=np.float64)
    store.dtypes["Sequential"] = "Int64"
    store.numeric["Sequential"] = True

    for name, dtype in zip(df.columns, df.dtypes):
        column = df[name]
        is_numeric = dtype.is_numeric()
        is_temporal = dtype in (pl.Date, pl.Datetime)

        if is_numeric:
            store.columns[name] = column.to_numpy()
        elif is_temporal:
            # Physical (integer) representation converts cleanly to a plottable numeric axis.
            store.columns[name] = column.to_physical().to_numpy().astype(np.float64)
        else:
            store.columns[name] = column.to_numpy()

        store.dtypes[name] = str(dtype)
        store.numeric[name] = is_numeric or is_temporal

    store.load_time_ms = (time.perf_counter() - start) * 1000
    return store
