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
        return [name for name in self.columns if self.numeric.get(name, False)]

    def get(self, name: str) -> np.ndarray:
        return self.columns[name]

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
