from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from csv_plot_maker.models.series import Series


@dataclass
class SubplotConfig:
    """One cell in the subplot grid: axis labels and series.

    X data is a per-series property (see Series.x_column) so a subplot can
    hold series from more than one file, each plotted against its own file's
    X -- but the bottom-axis *title* (x_label) and X pan/zoom sync
    (link_x_axis) still apply to the subplot/view as a whole.
    """

    row: int
    col: int
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
    # Whether this subplot's X pan/zoom is broadcast to every other subplot
    # that also has this on -- an opt-in group, not an all-or-nothing project
    # setting, so only the subplots actually sharing a comparable timeline
    # (e.g. two files' data aligned via X offset) need to be linked.
    link_x_axis: bool = False
    series: list[Series] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def add_series(self, series: Series) -> None:
        self.series.append(series)

    def remove_series(self, series_id: str) -> None:
        self.series = [s for s in self.series if s.id != series_id]

    def get_series(self, series_id: str) -> Series | None:
        return next((s for s in self.series if s.id == series_id), None)

    def x_signature(self) -> tuple[str, str, float] | None:
        """(source_id, x_column, x_offset) if every one of this subplot's
        series agrees on it, else None -- either because it mixes X
        references internally (series from more than one file, or the same
        file's columns/offsets set differently) or has no series at all.
        """
        signatures = {(s.source_id, s.x_column, s.x_offset) for s in self.series}
        return next(iter(signatures)) if len(signatures) == 1 else None

    def default_x_label(self) -> str:
        """The X column name to show when `x_label` hasn't been manually set
        -- the shared column name if every series agrees on one (the common
        case: one file, or several files all using the same column like
        "timestamp"), else blank rather than guessing.
        """
        signature = self.x_signature()
        return signature[1] if signature is not None else ""
