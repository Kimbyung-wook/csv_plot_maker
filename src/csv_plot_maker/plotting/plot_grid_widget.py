from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QPainter, QPicture

from csv_plot_maker.plotting.subplot_view import SubplotView


class PlotGridWidget(pg.GraphicsLayoutWidget):
    """Wraps a pyqtgraph GraphicsLayoutWidget. Rebuilt only when grid dims change.

    Also the drop target for drag-and-drop column assignment (a column dragged
    from the Data tab's list) and the source of subplot-selection-by-click, so
    the right-hand config panel can track "the subplot the user is looking at"
    without a separate selector.
    """

    subplot_clicked = Signal(int, int)  # row, col
    column_dropped = Signal(int, int, str)  # row, col, column name
    axis_label_double_clicked = Signal(int, int, str)  # row, col, "bottom"/"left"/"right"

    # Always-reserved px of room for a Y-axis title, whether or not a
    # subplot currently has one set. Reserving it unconditionally -- instead
    # of only once a title is actually typed in -- means typing one in or
    # clearing it never changes the axis width, so it never needs a re-sync
    # of its own (see SubplotView.set_labels).
    _TITLE_GUTTER = 20

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._views: dict[tuple[int, int], SubplotView] = {}
        self._background = "w"
        self._foreground = "k"
        self._link_x_axes = False
        self._syncing_x_range = False
        # Coalesces bursts of data/label changes (one per subplot on a grid
        # rebuild, one per replot, etc.) into a single re-sync on the next
        # spin of the event loop instead of one per call. Deliberately NOT
        # wired to sigYRangeChanged (interactive pan/zoom): re-measuring and
        # re-pinning every subplot's axis on every mouse-move-driven range
        # change made dragging/zooming visibly janky, and it's no longer
        # needed for the Y-axis title case anyway now that its space is
        # always reserved unconditionally (see _TITLE_GUTTER) instead of
        # only added reactively once a title is actually typed in.
        self._axis_sync_timer = QTimer(self)
        self._axis_sync_timer.setSingleShot(True)
        self._axis_sync_timer.setInterval(0)
        self._axis_sync_timer.timeout.connect(self._sync_left_axis_widths)
        self.setAcceptDrops(True)
        self.scene().sigMouseClicked.connect(self._on_scene_clicked)
        self.rebuild(1, 1)

    def rebuild(self, rows: int, cols: int) -> None:
        self.clear()
        self._views = {}
        for r in range(rows):
            for c in range(cols):
                plot_item = self.addPlot(row=r, col=c)
                view = SubplotView(plot_item)
                view.apply_theme(self._background, self._foreground)
                view.plot_item.vb.sigXRangeChanged.connect(
                    lambda _vb, x_range, rc=(r, c): self._on_view_x_range_changed(rc, x_range)
                )
                self._views[(r, c)] = view
        self.schedule_axis_width_sync()

    def schedule_axis_width_sync(self, *_args) -> None:
        """Queue a left-axis width re-sync on the next spin of the event loop.

        Call this after anything structural that can change how many digits
        a left axis's tick labels need: a grid rebuild, or a subplot's data/
        series changing (see MainWindow._replot_subplot). Deliberately not
        triggered by interactive pan/zoom -- see the constructor comment.
        """
        self._axis_sync_timer.start()

    def _sync_left_axis_widths(self) -> None:
        """Pin every subplot's left axis to the same width so their plot
        areas -- and therefore the left "wall" each one draws -- line up on
        the same vertical line, regardless of how many digits each
        subplot's own tick labels happen to need.
        """
        if not self._views:
            return
        axes = [view.plot_item.getAxis("left") for view in self._views.values()]
        for axis in axes:
            axis.setWidth(None)
            self._refresh_axis_text_width(axis)
        # Compute each axis's tick-only width ourselves (see
        # _tick_only_width) rather than reading back AxisItem's own
        # maximumWidth()/width(): those fold in AxisItem's *own* title-width
        # contribution, which only appears once a title is actually visible
        # -- so pinning to that value would still grow the axis reactively
        # the moment a title is typed in. Adding our own constant gutter to
        # a title-independent base means the width never depends on whether
        # a title happens to be set.
        max_width = max((self._tick_only_width(axis) for axis in axes), default=0)
        if max_width > 0:
            max_width += self._TITLE_GUTTER
            for axis in axes:
                axis.setWidth(max_width)

    @staticmethod
    def _tick_only_width(axis: pg.AxisItem) -> float:
        """AxisItem's own natural-width formula, minus its conditional title
        contribution (label.boundingRect().height() * 0.8 when a title is
        visible) -- see _TITLE_GUTTER for why that term is handled separately.
        """
        if not axis.isVisible() or not axis.style["showValues"]:
            return 0.0
        w = axis.textWidth if axis.style["autoExpandTextSpace"] else axis.style["tickTextWidth"]
        w += axis.style["tickTextOffset"][0]
        w += max(0, axis.style["tickLength"])
        return w

    @staticmethod
    def _refresh_axis_text_width(axis: pg.AxisItem) -> None:
        """Force AxisItem to (re)measure the width its *current* tick labels
        need, instead of trusting whatever it last measured.

        AxisItem only updates its cached natural width as a side effect of
        actually being painted by Qt, which is not guaranteed to have
        happened yet for this axis's current range right after a zoom/pan/
        data change -- e.g. immediately after zooming out to a range whose
        tick labels need more digits than before. Reading back a stale,
        too-narrow width here and then pinning every subplot's left axis to
        it (see _sync_left_axis_widths) is what clipped the newer, wider
        labels: once fixedWidth is set, AxisItem stops recomputing its own
        size from new tick content, so the too-small width would otherwise
        stick permanently. Running the same tick-drawing computation Qt's
        paint() would run, into a throwaway QPicture, forces that
        measurement to happen right now instead.
        """
        picture = QPicture()
        painter = QPainter(picture)
        try:
            if axis.style["tickFont"]:
                painter.setFont(axis.style["tickFont"])
            axis.generateDrawSpecs(painter)
        finally:
            painter.end()

    def get_view(self, row: int, col: int) -> SubplotView:
        return self._views[(row, col)]

    def views(self) -> dict[tuple[int, int], SubplotView]:
        return dict(self._views)

    def set_link_x_axes(self, enabled: bool) -> None:
        """When enabled, panning/zooming any subplot's X axis applies the same
        X range to every other subplot (their own Y axes are left untouched).
        """
        self._link_x_axes = enabled
        if enabled and self._views:
            reference_view = next(iter(self._views.values()))
            x_range = reference_view.plot_item.vb.viewRange()[0]
            self._broadcast_x_range(None, x_range)

    def _on_view_x_range_changed(self, rc: tuple[int, int], x_range) -> None:
        if not self._link_x_axes or self._syncing_x_range:
            return
        self._broadcast_x_range(rc, x_range)

    def _broadcast_x_range(self, source_rc: tuple[int, int] | None, x_range) -> None:
        self._syncing_x_range = True
        try:
            for rc, view in self._views.items():
                if rc == source_rc:
                    continue
                view.plot_item.setXRange(*x_range, padding=0)
        finally:
            self._syncing_x_range = False

    def set_theme_colors(self, background, foreground) -> None:
        """Push a light/dark theme into the plot area. Persists across rebuild()."""
        self._background = background
        self._foreground = foreground
        self.setBackground(background)
        for view in self._views.values():
            view.apply_theme(background, foreground)

    def _view_at_scene_pos(self, pos) -> tuple[int, int] | None:
        for (r, c), view in self._views.items():
            if view.plot_item.sceneBoundingRect().contains(pos):
                return (r, c)
        return None

    def _axis_at_scene_pos(self, pos) -> tuple[int, int, str] | None:
        for (r, c), view in self._views.items():
            for axis_name in ("bottom", "left", "right"):
                axis_item = view.plot_item.getAxis(axis_name)
                if axis_item.isVisible() and axis_item.sceneBoundingRect().contains(pos):
                    return (r, c, axis_name)
        return None

    def _on_scene_clicked(self, ev) -> None:
        if ev.double():
            axis_hit = self._axis_at_scene_pos(ev.scenePos())
            if axis_hit is not None:
                self.axis_label_double_clicked.emit(*axis_hit)
            return
        rc = self._view_at_scene_pos(ev.scenePos())
        if rc is not None:
            self.subplot_clicked.emit(*rc)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        # A multi-selected drag (Ctrl/Shift-click in the column list) carries
        # every selected column name, one per line -- add them all at once.
        columns = [c for c in event.mimeData().text().split("\n") if c]
        scene_pos = self.mapToScene(event.position().toPoint())
        rc = self._view_at_scene_pos(scene_pos)
        if rc is not None and columns:
            for column in columns:
                self.column_dropped.emit(rc[0], rc[1], column)
            event.acceptProposedAction()
