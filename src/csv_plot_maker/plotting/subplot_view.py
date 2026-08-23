from __future__ import annotations

import numpy as np
import pyqtgraph as pg

from csv_plot_maker.models.series import Series
from csv_plot_maker.plotting.style_map import make_pen, symbol_kwargs


class SubplotView:
    """Wraps one pyqtgraph PlotItem: incremental series/style/label updates.

    Style and label changes only touch the affected pyqtgraph item (setPen,
    setSymbol, setLabel) -- never a full data resend -- so they stay instant
    even with millions of points loaded.

    A secondary ViewBox is linked to the PlotItem's X axis (the standard
    pyqtgraph "multiple y-axis" recipe) so series can be routed to a right
    axis independent of the left one, per-series via `Series.axis`.
    """

    def __init__(self, plot_item: pg.PlotItem) -> None:
        self.plot_item = plot_item
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._curve_axis: dict[str, str] = {}
        # Grid lines are painted by the axis items (top/bottom/left/right),
        # which are siblings of the ViewBox in the scene tree, not children
        # of it -- and pyqtgraph adds the ViewBox to that shared parent
        # *before* the axis items, so by default the axis items (and their
        # grid) stack on top of the ViewBox's entire contents (every curve
        # and the legend). Push them behind explicitly so the grid is always
        # a background layer.
        for name in ("top", "bottom", "left", "right"):
            axis = self.plot_item.getAxis(name)
            axis.setZValue(-10)
            # pyqtgraph scales how many major/minor ticks it's willing to
            # draw down with the axis's pixel length, so a short axis (many
            # subplots stacked in one grid) can end up with only one or two
            # labeled gridlines even when the visible Y range spans a much
            # larger scale -- e.g. only "0" showing for a range that goes up
            # to several thousand. Raising the density keeps enough ticks to
            # actually read the range at any zoom level or grid size.
            axis.setTickDensity(1.75)

        self.plot_item.addLegend()
        # Within the ViewBox's own children, later-added items stack on top
        # -- and curves get added after the legend -- so without this the
        # legend's box can still be drawn over by a curve line passing
        # underneath it. Keep the legend above everything else in the plot.
        self.plot_item.legend.setZValue(1000)
        self.plot_item.showGrid(x=True, y=True, alpha=0.25)

        self.right_vb = pg.ViewBox()
        self.plot_item.showAxis("right")
        self.plot_item.scene().addItem(self.right_vb)
        self.plot_item.getAxis("right").linkToView(self.right_vb)
        self.right_vb.setXLink(self.plot_item)
        self._update_right_axis_visibility()

        self.plot_item.vb.sigResized.connect(self._sync_right_view_geometry)

    def _sync_right_view_geometry(self) -> None:
        self.right_vb.setGeometry(self.plot_item.vb.sceneBoundingRect())
        self.right_vb.linkedViewChanged(self.plot_item.vb, self.right_vb.XAxis)

    def set_series_data(self, series: Series, x: np.ndarray, y: np.ndarray) -> None:
        curve = self._curves.get(series.id)
        if curve is not None and self._curve_axis.get(series.id) != series.axis:
            # axis reassigned: the curve must move to the other ViewBox.
            self.remove_series(series.id)
            curve = None

        if curve is None:
            pen = make_pen(series)
            sym = symbol_kwargs(series)
            curve = pg.PlotDataItem(x, y, pen=pen, name=series.y_column, **sym)
            if series.axis == "secondary":
                self.right_vb.addItem(curve)
                # ViewBox.addItem (unlike PlotItem.addItem) doesn't know about the
                # legend, so secondary-axis curves need to be registered by hand.
                if self.plot_item.legend is not None:
                    self.plot_item.legend.addItem(curve, series.y_column)
            else:
                # PlotItem.addItem already registers named items with the legend
                # itself -- an extra manual addItem() here would double the entry.
                self.plot_item.addItem(curve)
            # Must be set only after the curve has a real ViewBox parent: pyqtgraph's
            # clipToView path calls view.autoRangeEnabled() on whatever getViewBox()
            # resolves to, and during addItem() the item briefly resolves to the
            # enclosing GraphicsView (no autoRangeEnabled) before its ViewBox parent
            # is attached -- enabling clipToView beforehand crashes on that transient state.
            curve.setDownsampling(auto=True, method="peak")
            curve.setClipToView(True)
            self._curves[series.id] = curve
            self._curve_axis[series.id] = series.axis
            self._update_right_axis_visibility()
        else:
            curve.setData(x, y)
            self._apply_style(curve, series)

    def update_series_style(self, series: Series) -> None:
        curve = self._curves.get(series.id)
        if curve is not None:
            self._apply_style(curve, series)

    def remove_series(self, series_id: str) -> None:
        curve = self._curves.pop(series_id, None)
        axis = self._curve_axis.pop(series_id, "primary")
        if curve is not None:
            if self.plot_item.legend is not None:
                self.plot_item.legend.removeItem(curve)
            if axis == "secondary":
                self.right_vb.removeItem(curve)
            else:
                self.plot_item.removeItem(curve)
            self._update_right_axis_visibility()

    def set_labels(self, x_label: str, y_label_left: str, y_label_right: str = "") -> None:
        self.plot_item.setLabel("bottom", x_label)
        self.plot_item.setLabel("left", y_label_left)
        # The left axis's width is a fixed constant regardless of whether a
        # title is set (see PlotGridWidget._TITLE_GUTTER), so typing one in
        # or clearing it never actually changes the axis's pixel geometry --
        # which means Qt's own resizeEvent (the only place pyqtgraph
        # repositions the rotated title text) never fires, leaving a
        # freshly-typed title vertically off-center against stale geometry.
        self._recenter_left_axis_label()
        # PlotItem.setLabel() unconditionally calls showAxis() as a side
        # effect, even for an empty label -- so without this, relabeling
        # (which happens on every replot: adding a series, editing any axis
        # label, changing the X column...) would force the right axis back
        # on regardless of whether any series actually uses it.
        self.plot_item.setLabel("right", y_label_right)
        self._update_right_axis_visibility()

    def _recenter_left_axis_label(self) -> None:
        # Mirrors AxisItem.resizeEvent()'s own centering formula for a
        # "left"-orientation label rather than calling resizeEvent() itself:
        # doing that manually (outside a real Qt-triggered resize) was found
        # to occasionally recurse into sizeHint()/boundingRect() in a way
        # that raised RuntimeErrors during widget teardown.
        axis = self.plot_item.getAxis("left")
        if axis.label is None:
            return
        br = axis.label.boundingRect()
        axis.label.setPos(-5, axis.size().height() / 2 + br.width() / 2)

    def set_legend_visible(self, visible: bool) -> None:
        if self.plot_item.legend is not None:
            self.plot_item.legend.setVisible(visible)

    def apply_theme(self, background, foreground) -> None:
        """Recolor axis lines/ticks/labels and the legend for a theme switch.

        Also gives the legend a fully opaque background box (matching the
        plot's own background, not a translucent tint of it) + border instead
        of pyqtgraph's default fully-transparent one, so grid lines and
        curves never show through underneath the legend text.
        """
        for name in ("bottom", "left", "right"):
            axis = self.plot_item.getAxis(name)
            axis.setPen(foreground)
            axis.setTextPen(foreground)

        legend = self.plot_item.legend
        if legend is not None:
            legend.setLabelTextColor(foreground)
            # LegendItem.setLabelTextColor() only updates each label's stored
            # opts -- it never re-renders the QGraphicsTextItem's cached HTML,
            # so already-added entries silently keep their old (often now
            # illegible) color unless setText() is re-run to rebuild it.
            for _sample, label in legend.items:
                label.setText(label.text)

            box_color = pg.mkColor(background)
            box_color.setAlpha(255)
            legend.setBrush(box_color)
            legend.setPen(foreground)

    def clear(self) -> None:
        for series_id in list(self._curves.keys()):
            self.remove_series(series_id)

    def _update_right_axis_visibility(self) -> None:
        has_secondary = any(axis == "secondary" for axis in self._curve_axis.values())
        axis_item = self.plot_item.getAxis("right")
        if has_secondary:
            axis_item.show()
            axis_item.setGrid(self.plot_item.ctrl.gridAlphaSlider.value())
        else:
            axis_item.hide()
            # A hidden axis doesn't paint on its own, but explicitly zeroing
            # its grid too means a subplot with no secondary-axis series
            # never has stray right-axis ticks/gridlines, even across a
            # theme change or a state reload that touches this axis again.
            axis_item.setGrid(False)

    @staticmethod
    def _apply_style(curve: pg.PlotDataItem, series: Series) -> None:
        curve.setPen(make_pen(series))
        sym = symbol_kwargs(series)
        curve.setSymbol(sym["symbol"])
        curve.setSymbolBrush(sym["symbolBrush"])
        curve.setSymbolPen(sym["symbolPen"])
        curve.setSymbolSize(sym["symbolSize"])
