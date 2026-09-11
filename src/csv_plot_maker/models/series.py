from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import numpy as np

if TYPE_CHECKING:
    from csv_plot_maker.models.data_source import DataSource

LineStyle = Literal["solid", "dash", "dot", "dashdot"]
Axis = Literal["primary", "secondary"]


@dataclass
class Series:
    """One plotted line: a Y column with an axis assignment and visual style.

    Identified by `id`, not by column name, so the same column can be added
    as multiple independent series (duplicate selection requirement).
    """

    y_column: str
    source_id: str = ""
    # This series' own X data -- always a column from `source_id` (the same
    # file its Y data comes from), never a different one: pairing X/Y from
    # two different files almost never has matching row counts, so a subplot
    # mixing files needs each series to carry its own X, not one shared per
    # subplot (see MainWindow._series_x_data).
    x_column: str = ""
    x_offset: float = 0.0
    axis: Axis = "primary"
    color: str = "#1f77b4"
    line_style: LineStyle = "solid"
    marker: str | None = None
    width: float = 1.5
    scale: float = 1.0
    offset: float = 0.0
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def is_ready(self, source: DataSource | None) -> bool:
        """False while this series has no X column chosen yet, or `source`
        (its own file, looked up by the caller from `source_id`) isn't open
        and fully loaded -- e.g. right after Load Layout queued an auto-
        reopen for a file that isn't open yet.
        """
        if not self.x_column:
            return False
        return source is not None and source.store is not None

    def x_data(self, source: DataSource) -> np.ndarray:
        """`source` must be this series' own, already-loaded source (see is_ready)."""
        return source.store.get(self.x_column) + self.x_offset

    def y_data(self, source: DataSource) -> np.ndarray:
        """`source` must be this series' own, already-loaded source (see is_ready)."""
        return source.store.get(self.y_column) * self.scale + self.offset
