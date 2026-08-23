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
