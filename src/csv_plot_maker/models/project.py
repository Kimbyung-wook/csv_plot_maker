from __future__ import annotations

from dataclasses import dataclass, field

from csv_plot_maker.models.subplot import SubplotConfig


@dataclass
class ProjectState:
    """Top-level app state: the loaded CSV path and the full subplot grid."""

    csv_path: str | None = None
    grid_rows: int = 1
    grid_cols: int = 1
    active_subplot_id: str | None = None
    subplots: list[SubplotConfig] = field(default_factory=list)
    link_x_axes: bool = False

    def build_default_grid(self) -> None:
        self.subplots = [
            SubplotConfig(row=r, col=c)
            for r in range(self.grid_rows)
            for c in range(self.grid_cols)
        ]
        self.active_subplot_id = self.subplots[0].id if self.subplots else None

    def get_active_subplot(self) -> SubplotConfig | None:
        return next((sp for sp in self.subplots if sp.id == self.active_subplot_id), None)

    def resize_grid(self, rows: int, cols: int) -> None:
        """Rebuild the grid, preserving existing subplot configs by (row, col) position."""
        old_by_pos = {(sp.row, sp.col): sp for sp in self.subplots}
        self.grid_rows = rows
        self.grid_cols = cols
        self.subplots = [
            old_by_pos.get((r, c), SubplotConfig(row=r, col=c))
            for r in range(rows)
            for c in range(cols)
        ]
        if self.active_subplot_id not in {sp.id for sp in self.subplots}:
            self.active_subplot_id = self.subplots[0].id if self.subplots else None
