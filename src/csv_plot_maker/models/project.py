from __future__ import annotations

from dataclasses import dataclass, field

from csv_plot_maker.models.data_source import UNASSIGNED_SOURCE_ID, DataSource, SourceRef
from csv_plot_maker.models.subplot import SubplotConfig


@dataclass
class ProjectState:
    """Top-level app state: the loaded CSV path and the full subplot grid."""

    csv_path: str | None = None
    grid_rows: int = 1
    grid_cols: int = 1
    active_subplot_id: str | None = None
    subplots: list[SubplotConfig] = field(default_factory=list)
    legend_font_size: int = 9
    # Every open file's identity (id/path/label/color) at the time this
    # project was saved, so Load Layout can re-open exactly the same files
    # under the same ids/colors instead of leaving every subplot/series'
    # source_id dangling. Absent (empty) for a single-CSV-era layout saved
    # before this existed.
    data_sources: list[SourceRef] = field(default_factory=list)

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

    def has_shared_x_axis(self) -> bool:
        """True when every subplot plots the exact same X data -- same file,
        same column, *and* same offset -- and each subplot is itself
        internally uniform (no mixed-file/mixed-column series within one
        subplot; see SubplotConfig.x_signature).
        """
        if not self.subplots:
            return False
        signatures = [sp.x_signature() for sp in self.subplots]
        first = signatures[0]
        if first is None or not first[1]:
            return False
        return all(sig == first for sig in signatures)

    def effective_x_label(self, subplot: SubplotConfig) -> str:
        """The bottom-axis title to actually show for `subplot`.

        When every subplot shares the same X data, only the bottom-most row
        needs its own axis title repeated -- every other row's is blanked
        out (not just left at its default) so pyqtgraph's AxisItem reserves
        no height for it, growing every subplot's plot area vertically. Once
        the subplots' X columns/offsets diverge again, every row gets its
        own title back automatically (this is recomputed on every replot,
        never stored as a one-off decision).
        """
        label = subplot.x_label or subplot.default_x_label()
        is_bottom_row = subplot.row == self.grid_rows - 1
        if self.has_shared_x_axis() and not is_bottom_row:
            return ""
        return label

    def prune_invalid_series(self, open_sources: dict[str, DataSource]) -> int:
        """Remove any series that names a Y or X column not actually present
        in its own, already-loaded source -- e.g. a loaded layout was saved
        against a slightly different version of that file. A reference to a
        source that hasn't finished loading yet (or was never resolved to
        any open file at all) is left alone here -- it either resolves once
        that load finishes, or gets cleaned up once that load ultimately
        fails (see the caller).

        Returns how many series were dropped.
        """
        dropped = 0
        for subplot in self.subplots:
            kept = []
            for series in subplot.series:
                source = open_sources.get(series.source_id)
                if source is not None and source.store is not None:
                    names = source.store.numeric_column_names()
                    if series.y_column not in names or (series.x_column and series.x_column not in names):
                        dropped += 1
                        continue
                kept.append(series)
            subplot.series = kept
        return dropped

    def reconcile_data_sources(self, open_sources: dict[str, DataSource]) -> list[SourceRef]:
        """After this project has just been loaded from a saved layout, match
        every source it references (self.data_sources) against the files
        already open (by path, since ids are assigned fresh each session) --
        remapping old ids in every subplot's series to whichever
        currently-open source shares that path.

        Returns the SourceRefs that still need to be (re)opened, each
        carrying its original id/label/color so subplot/series references
        resolve once it loads -- actually loading them is the caller's job,
        since this model has no notion of how a file gets opened.
        """
        open_by_path = {s.path: s.id for s in open_sources.values()}
        id_remap: dict[str, str] = {}
        to_load: list[SourceRef] = []
        for ref in self.data_sources:
            matched_id = open_by_path.get(ref.path)
            if matched_id is not None:
                if matched_id != ref.id:
                    id_remap[ref.id] = matched_id
            elif ref.id not in open_sources:
                to_load.append(ref)

        if not self.data_sources and open_sources:
            # Pre-multi-CSV layout: every series/x-column implicitly
            # referred to "the one CSV that's open" -- attach those bare
            # references to whichever source is currently open, matching
            # old single-CSV semantics exactly.
            fallback = next(iter(open_sources.values()))
            id_remap[UNASSIGNED_SOURCE_ID] = fallback.id

        if id_remap:
            for subplot in self.subplots:
                for series in subplot.series:
                    series.source_id = id_remap.get(series.source_id, series.source_id)

        return to_load
