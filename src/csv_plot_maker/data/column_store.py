from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ColumnStore:
    """Holds one CSV's columns as numpy arrays, shared/reused across duplicate series."""

    columns: dict[str, np.ndarray] = field(default_factory=dict)
    dtypes: dict[str, str] = field(default_factory=dict)
    numeric: dict[str, bool] = field(default_factory=dict)
    row_count: int = 0
    source_path: str | None = None
    load_time_ms: float = 0.0

    def column_names(self) -> list[str]:
        return list(self.columns.keys())

    def numeric_column_names(self) -> list[str]:
        # .get(name, False) rather than self.numeric[name]: loader.py always
        # sets a numeric flag for every name it adds to `columns` (whether
        # via set_column's own is_numeric or an earlier set_metadata call),
        # so this default is never actually exercised by a real load -- kept
        # only as a cheap guard against a hand-built ColumnStore (e.g. a test
        # fixture) that populated `columns` directly without `numeric` too.
        return [name for name in self.columns if self.numeric.get(name, False)]

    def get(self, name: str) -> np.ndarray:
        return self.columns[name]

    def set_metadata(self, name: str, dtype: str, is_numeric: bool) -> None:
        """Register a column's dtype/numeric-ness ahead of (or instead of,
        for a column that turns out not to be plottable) storing its array
        -- see set_column. Keeping both writes behind named methods, rather
        than loader.py poking `dtypes`/`numeric` directly, is what keeps
        these two dicts (plus `columns`) from drifting out of sync.
        """
        self.dtypes[name] = dtype
        self.numeric[name] = is_numeric

    def set_numeric(self, name: str, is_numeric: bool) -> None:
        """Override a column's numeric flag after the fact -- e.g. a String
        column recovered as actually-numeric-text once every value is in
        hand (see loader.py's echo-field recovery).
        """
        self.numeric[name] = is_numeric

    def set_column(self, name: str, array: np.ndarray, dtype: str | None = None, is_numeric: bool | None = None) -> None:
        """Store `name`'s parsed array, optionally setting its dtype/numeric
        metadata in the same call (when they weren't already registered via
        set_metadata beforehand).
        """
        self.columns[name] = array
        if dtype is not None:
            self.dtypes[name] = dtype
        if is_numeric is not None:
            self.numeric[name] = is_numeric

    def is_empty(self) -> bool:
        return not self.columns

    def total_nbytes(self) -> int:
        """Sum of every stored column array's memory footprint, in bytes."""
        return sum(arr.nbytes for arr in self.columns.values())

    def is_sparse(self, name: str, threshold: float = 0.5) -> bool:
        """True if more than `threshold` of the column's values are missing (NaN).

        Used to pick a sensible default series style: a mostly-empty column
        (e.g. a rarely-updated periodic "echo" status field) has its few real
        samples scattered far enough apart that a plain connecting line never
        has two adjacent finite points to draw between -- nothing renders at
        all unless a marker highlights each point individually.
        """
        arr = self.columns[name]
        if arr.dtype.kind != "f" or arr.size == 0:
            return False
        return float(np.isnan(arr).mean()) > threshold
