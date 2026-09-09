from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from csv_plot_maker.models.series import Series


@dataclass
class SubplotConfig:
    """One cell in the subplot grid: its own X column, axis labels, and series."""

    row: int
    col: int
    x_column: str | None = None
    x_offset: float = 0.0
    x_label: str = ""
    y_label_left: str = ""
    y_label_right: str = ""
    # [min, max] of the primary/secondary Y axis as last seen on screen, so
    # a manual zoom/pan survives Save Layout / Load Layout -- None means "no
    # saved view yet, autorange to fit the data" (a freshly built subplot,
    # or one with no series to have a view over in the first place).
    y_range_left: list[float] | None = None
    y_range_right: list[float] | None = None
    show_legend: bool = True
    series: list[Series] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def add_series(self, series: Series) -> None:
        self.series.append(series)

    def remove_series(self, series_id: str) -> None:
        self.series = [s for s in self.series if s.id != series_id]

    def get_series(self, series_id: str) -> Series | None:
        return next((s for s in self.series if s.id == series_id), None)
