from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore

from csv_plot_maker.models.series import Series
from csv_plot_maker.plotting.style_map import make_pen, symbol_kwargs

# The pt size at which pyqtgraph's own built-in legend icon size (20x20px,
# see ItemSample.__init__) already looks right -- this app's own "Medium"
# legend size default, so scaling around it leaves Medium/Large unchanged.
_LEGEND_SAMPLE_REFERENCE_PT = 9
_LEGEND_SAMPLE_MAX_PX = 20
_LEGEND_SAMPLE_MIN_PX = 8
# Tiny (5pt) hand-tuned smaller than the proportional formula below would
# give (round(20 * 5 / 9) == 11) -- asked for explicitly, rather than
# recalibrating the formula itself and nudging Small's icon size too.
_LEGEND_SAMPLE_SIZE_OVERRIDES: dict[int, int] = {5: 9}

# Fallback for _current_grid_alpha() if pyqtgraph's own internal
# PlotItem.ctrl.gridAlphaSlider (undocumented, not part of its public API)
# is ever missing/renamed by a future pyqtgraph version -- matches this
# app's own showGrid(alpha=0.25) call in SubplotView.__init__, so the
# fallback still looks the same as what every plot is actually set up with.
_DEFAULT_GRID_ALPHA = 0.25


def _legend_sample_size(size_pt: int) -> int:
    if size_pt in _LEGEND_SAMPLE_SIZE_OVERRIDES:
        return _LEGEND_SAMPLE_SIZE_OVERRIDES[size_pt]
    return max(_LEGEND_SAMPLE_MIN_PX, min(_LEGEND_SAMPLE_MAX_PX, round(_LEGEND_SAMPLE_MAX_PX * size_pt / _LEGEND_SAMPLE_REFERENCE_PT)))


def _format_transform_number(value: float) -> str:
    return f"{value:g}"


def _legend_name(series: Series, label_prefix: str = "") -> str:
    """The legend entry text for one series: just the column name at the
    default scale=1/offset=0, or the column name plus a short summary of
    the applied linear transform (transformed = raw * scale + offset)
    otherwise -- so a viewer can tell a curve isn't showing raw values
    without having to reopen the style panel.

    `label_prefix` (e.g. "flight1.csv: ") is prepended whenever the owning
    subplot mixes series from more than one open file -- see
    MainWindow._legend_prefix_for -- and left empty (the common case) when
    every series in that subplot comes from the same file.
    """
    if series.scale == 1.0 and series.offset == 0.0:
        base = series.y_column
    else:
        bits = []
        if series.scale != 1.0:
            bits.append(f"×{_format_transform_number(series.scale)}")
        if series.offset != 0.0:
            sign = "+" if series.offset >= 0 else "−"
            bits.append(f"{sign}{_format_transform_number(abs(series.offset))}")
        base = f"{series.y_column} ({' '.join(bits)})"
    return f"{label_prefix}{base}"


class _ScalableItemSample(pg.ItemSample):
    """pyqtgraph's legend icon (the line/marker swatch next to each entry's
    text), but its square scales down for small legend fonts instead of
    staying a fixed 20x20px.

    Below the Medium (9pt) legend size, that fixed 20px icon ends up taller
    than the now-smaller text next to it, so the icon alone pins the row's
    height -- shrinking the font further (e.g. to Tiny) stops shrinking the
    row/entry spacing even though the text keeps getting smaller. Default
    size is a class attribute (not passed through the constructor) because
    pyqtgraph's own LegendItem.addItem() always instantiates a sample as
    `self.sampleType(item)` -- no room to pass a size in -- so
    SubplotView.set_legend_font_size() sets this class attribute before
    resizing already-added samples, and any newly-added curve's icon then
    starts out already correctly sized.
    """

    default_size = _LEGEND_SAMPLE_MAX_PX

    def __init__(self, item) -> None:
        super().__init__(item)
        self.set_size(type(self).default_size)

    def set_size(self, size: int) -> None:
        self._size = size
        self.setFixedWidth(size)
        self.setFixedHeight(size)
        self.update()

    def boundingRect(self) -> QtCore.QRectF:
        return QtCore.QRectF(0, 0, self._size, self._size)

    def paint(self, p, *args) -> None:
        # The inherited paint() draws at coordinates calibrated for a fixed
        # 20x20 box (e.g. the pen-sample line runs from (0, 11) to (20, 11))
        # -- scale the painter to this instance's actual size instead of
        # reimplementing every coordinate for an arbitrary box size. A
        # no-op (scale factor 1) whenever _size is still the default 20.
        p.save()
        scale = self._size / _LEGEND_SAMPLE_MAX_PX
        p.scale(scale, scale)
        super().paint(p, *args)
        p.restore()


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
        self._curve_legend_names: dict[str, str] = {}
        self._foreground = pg.mkColor("k")
        self._torn_down = False
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

        # pyqtgraph's LegendItem defaults to a 9px margin on all four sides
        # plus 5px between each entry's color swatch and its text -- fine for
        # a single large plot, but with many small subplots stacked in a
        # grid the legend box ends up disproportionately large next to the
        # data it's labeling. Tighten both.
        self.plot_item.addLegend(horSpacing=3, verSpacing=0, sampleType=_ScalableItemSample)
        legend = self.plot_item.legend
        legend.layout.setContentsMargins(4, 4, 4, 4)
        # Within the ViewBox's own children, later-added items stack on top
        # -- and curves get added after the legend -- so without this the
        # legend's box can still be drawn over by a curve line passing
        # underneath it. Keep the legend above everything else in the plot.
        legend.setZValue(1000)
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

    def set_series_data(self, series: Series, x: np.ndarray, y: np.ndarray, label_prefix: str = "") -> None:
        curve = self._curves.get(series.id)
        if curve is not None and self._curve_axis.get(series.id) != series.axis:
            # axis reassigned: the curve must move to the other ViewBox.
            self.remove_series(series.id)
            curve = None

        if curve is None:
            pen = make_pen(series)
            sym = symbol_kwargs(series)
            name = _legend_name(series, label_prefix)
            curve = pg.PlotDataItem(x, y, pen=pen, name=name, **sym)
            self._curve_legend_names[series.id] = name
            if series.axis == "secondary":
                self.right_vb.addItem(curve)
                # ViewBox.addItem (unlike PlotItem.addItem) doesn't know about the
                # legend, so secondary-axis curves need to be registered by hand.
                if self.plot_item.legend is not None:
                    self.plot_item.legend.addItem(curve, name)
            else:
                # PlotItem.addItem already registers named items with the legend
                # itself -- an extra manual addItem() here would double the entry.
                self.plot_item.addItem(curve)
            # Must be set only after the curve has a real ViewBox parent: pyqtgraph's
            # clipToView path calls view.autoRangeEnabled() on whatever getViewBox()
            # resolves to, and during addItem() the item briefly resolves to the
            # enclosing GraphicsView (no autoRangeEnabled) before its ViewBox parent
            # is attached -- enabling clipToView beforehand crashes on that transient state.
            self._apply_downsampling(curve, series)
            curve.setClipToView(True)
            self._curves[series.id] = curve
            self._curve_axis[series.id] = series.axis
            self._update_right_axis_visibility()
        else:
            curve.setData(x, y)
            self._apply_style(curve, series)
            self._sync_legend_name(series, label_prefix)

    def _sync_legend_name(self, series: Series, label_prefix: str = "") -> None:
        curve = self._curves.get(series.id)
        legend = self.plot_item.legend
        if curve is None or legend is None:
            return
        name = _legend_name(series, label_prefix)
        if self._curve_legend_names.get(series.id) == name:
            return
        self._curve_legend_names[series.id] = name
        for sample, label in legend.items:
            if sample.item is curve:
                label.setText(name)
                break

    def update_series_style(self, series: Series) -> None:
        curve = self._curves.get(series.id)
        if curve is not None:
            self._apply_style(curve, series)

    def remove_series(self, series_id: str) -> None:
        curve = self._curves.pop(series_id, None)
        axis = self._curve_axis.pop(series_id, "primary")
        self._curve_legend_names.pop(series_id, None)
        if curve is not None:
            if self.plot_item.legend is not None:
                self.plot_item.legend.removeItem(curve)
            if axis == "secondary":
                self.right_vb.removeItem(curve)
            else:
                self.plot_item.removeItem(curve)
            self._update_right_axis_visibility()

    def get_x_range(self) -> tuple[float, float]:
        lo, hi = self.plot_item.vb.viewRange()[0]
        return (lo, hi)

    def get_y_range(self, secondary: bool = False) -> tuple[float, float]:
        vb = self.right_vb if secondary else self.plot_item.vb
        lo, hi = vb.viewRange()[1]
        return (lo, hi)

    def set_x_range(self, x_min: float, x_max: float, padding: float = 0.0) -> None:
        self.plot_item.setXRange(x_min, x_max, padding=padding)

    def set_y_range(self, y_min: float, y_max: float, secondary: bool = False, padding: float = 0.0) -> None:
        if secondary:
            self.right_vb.setYRange(y_min, y_max, padding=padding)
        else:
            self.plot_item.setYRange(y_min, y_max, padding=padding)

    def set_bottom_label(self, x_label: str) -> None:
        """Just the bottom-axis title, without touching left/right -- for
        MainWindow._sync_x_axis_titles, which re-evaluates every subplot's
        title on each replot and would otherwise have to resend the (already
        current) Y labels too just to reach this one.
        """
        self.plot_item.setLabel("bottom", x_label)

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
        # Same reasoning as the left axis just above: the right axis's width
        # is also pinned to a fixed constant whenever any subplot in the grid
        # uses a secondary axis (see PlotGridWidget._sync_right_axis_widths),
        # so typing a title in doesn't change its geometry either and Qt's
        # resizeEvent won't fire on its own to recenter it.
        self._recenter_right_axis_label()
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

    def _recenter_right_axis_label(self) -> None:
        # Mirrors AxisItem.resizeEvent()'s own centering formula for a
        # "right"-orientation label -- see _recenter_left_axis_label for why
        # resizeEvent() itself isn't called directly.
        axis = self.plot_item.getAxis("right")
        if axis.label is None:
            return
        br = axis.label.boundingRect()
        axis.label.setPos(axis.size().width() - br.height() + 5, axis.size().height() / 2 + br.width() / 2)

    def set_legend_visible(self, visible: bool) -> None:
        if self.plot_item.legend is not None:
            self.plot_item.legend.setVisible(visible)

    def set_legend_font_size(self, size_pt: int) -> None:
        legend = self.plot_item.legend
        if legend is None:
            return
        legend.setLabelTextSize(f"{size_pt}pt")
        # LegendItem.setLabelTextSize() only updates each label's stored opts
        # -- like setLabelTextColor() (see apply_theme), it never re-renders
        # the QGraphicsTextItem's cached HTML on its own.
        sample_px = _legend_sample_size(size_pt)
        # A class attribute, not per-instance state: pyqtgraph's own
        # LegendItem.addItem() always builds a fresh sample as
        # `self.sampleType(item)` with no way to pass a size in, so this is
        # what makes any curve added *after* this point start out already
        # sized correctly instead of at the 20px default.
        _ScalableItemSample.default_size = sample_px
        for sample, label in legend.items:
            label.setText(label.text)
            sample.set_size(sample_px)
        self._resize_legend_to_fit(legend)

    @staticmethod
    def _resize_legend_to_fit(legend: pg.LegendItem) -> None:
        """Recompute the legend box's own outer size from its current
        content, replacing pyqtgraph's own LegendItem.updateSize().

        updateSize() sums each entry's *current* item.width()/height() but
        never adds the layout's own contentsMargins into the outer size it
        sets -- harmless with pyqtgraph's zero-ish default margins, but once
        a real margin is set (see __init__) it makes the box a few pixels
        too small for its own padding. Since each entry's size policy lets
        it stretch to fill whatever room activate() gives it, the next
        resize measures those now-compressed items and shrinks the box
        again -- a self-reinforcing loop that made repeatedly picking the
        same (e.g. "Small") legend font size keep shrinking the box further
        each time instead of settling. Reading each item's own
        `effectiveSizeHint(PreferredSize)` -- which reflects the text's true
        natural size regardless of whatever the box's current geometry
        happens to be -- and adding the margins back in makes this
        idempotent: repeating the same font size always converges to the
        same size in one pass.
        """
        layout = legend.layout
        left, top, right, bottom = layout.getContentsMargins()
        width = 0.0
        height = 0.0
        for row in range(layout.rowCount()):
            row_height = 0.0
            col_width = 0.0
            for col in range(layout.columnCount()):
                item = layout.itemAt(row, col)
                if item is None:
                    continue
                hint = item.effectiveSizeHint(QtCore.Qt.SizeHint.PreferredSize, QtCore.QSizeF())
                col_width += hint.width() + 3
                row_height = max(row_height, hint.height())
            width = max(width, col_width)
            height += row_height
        legend.setGeometry(0, 0, width + left + right, height + top + bottom)

    def apply_theme(self, background, foreground) -> None:
        """Recolor axis lines/ticks/labels and the legend for a theme switch.

        Also gives the legend a fully opaque background box (matching the
        plot's own background, not a translucent tint of it) + border instead
        of pyqtgraph's default fully-transparent one, so grid lines and
        curves never show through underneath the legend text.
        """
        self._foreground = pg.mkColor(foreground)
        for name in ("bottom", "left"):
            axis = self.plot_item.getAxis(name)
            axis.setPen(foreground)
            axis.setTextPen(foreground)
        self._update_right_axis_visibility()

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

    def teardown(self) -> None:
        """Release the secondary ViewBox before this SubplotView is discarded.

        Undoes __init__'s setup in reverse order:

        1. clear() every curve -- including ones parented under right_vb --
           so none are left dangling off it once it's gone.
        2. setXLink(None) to undo right_vb.setXLink(plot_item) from
           __init__: pyqtgraph's linkView() wires sigResized/range-changed
           signal connections *from* plot_item.vb *to* right_vb's own bound
           methods, which otherwise keeps right_vb alive (and reachable from
           a still-live plot_item.vb) after this SubplotView's own
           references to it are dropped.
        3. disconnect our own sigResized hookup.
        4. remove right_vb from the scene.

        right_vb was added directly to the scene (see __init__) rather than
        parented under plot_item, so plot_item's own removal from the scene
        (PlotGridWidget.rebuild -> GraphicsLayout.clear) does not take it or
        any curves still attached to it along. Skipping any of the steps
        above leaves right_vb's Python object reachable (and thus not yet
        garbage-collected) through one of these live Qt-side connections
        right up until plot_item.vb itself is torn down -- at which point
        both can end up deleted in an order Python's refcounting doesn't
        control, and a paint/layout event already queued for right_vb that
        arrives after Python has dropped it raises "libshiboken: Internal
        C++ object (ViewBox) already deleted" instead of a clean teardown.

        Idempotent: a second call (or a call after the view was already
        partially torn down) is a no-op instead of raising, since
        setXLink(None)/disconnect() both fail with RuntimeError against an
        already-unlinked/-disconnected or already-deleted C++ side.
        """
        if self._torn_down:
            return
        self._torn_down = True
        self.clear()
        self.right_vb.setXLink(None)
        self.plot_item.vb.sigResized.disconnect(self._sync_right_view_geometry)
        scene = self.plot_item.scene()
        if scene is not None:
            scene.removeItem(self.right_vb)

    def has_secondary_series(self) -> bool:
        return any(axis == "secondary" for axis in self._curve_axis.values())

    def _current_grid_alpha(self) -> float:
        """The grid transparency the user last set via the plot's own
        right-click context menu (pyqtgraph's own UI, not this app's) --
        read from its internal gridAlphaSlider widget so the right axis'
        grid (see _update_right_axis_visibility) matches the left/bottom
        axes' grid exactly. `ctrl.gridAlphaSlider` is an undocumented
        internal of pyqtgraph's PlotItem, not its public API, so this falls
        back to this app's own default instead of raising if a future
        pyqtgraph version renames or removes it.
        """
        try:
            return self.plot_item.ctrl.gridAlphaSlider.value()
        except AttributeError:
            return _DEFAULT_GRID_ALPHA

    def _update_right_axis_visibility(self) -> None:
        has_secondary = self.has_secondary_series()
        axis_item = self.plot_item.getAxis("right")
        # Kept permanently shown (never axis_item.hide()) rather than toggled:
        # AxisItem forces its own width to 0 whenever isVisible() is False,
        # regardless of any fixedWidth pinned onto it, which would zero out
        # the reserved space PlotGridWidget._sync_right_axis_widths() pins
        # here to keep every subplot's column the same width even when only
        # one subplot in the grid actually uses a secondary axis. When unused,
        # blank it out instead -- fully transparent pen, no tick values, no
        # label, no grid -- so nothing actually renders even though the
        # layout still reserves its width.
        axis_item.show()
        if has_secondary:
            axis_item.setStyle(showValues=True)
            axis_item.setPen(self._foreground)
            axis_item.setTextPen(self._foreground)
            axis_item.setGrid(self._current_grid_alpha())
        else:
            transparent = pg.mkColor(0, 0, 0, 0)
            axis_item.setStyle(showValues=False)
            axis_item.setPen(transparent)
            axis_item.setTextPen(transparent)
            axis_item.showLabel(False)
            axis_item.setGrid(False)

    @staticmethod
    def _apply_style(curve: pg.PlotDataItem, series: Series) -> None:
        curve.setPen(make_pen(series))
        sym = symbol_kwargs(series)
        curve.setSymbol(sym["symbol"])
        curve.setSymbolBrush(sym["symbolBrush"])
        curve.setSymbolPen(sym["symbolPen"])
        curve.setSymbolSize(sym["symbolSize"])
        SubplotView._apply_downsampling(curve, series)

    @staticmethod
    def _apply_downsampling(curve: pg.PlotDataItem, series: Series) -> None:
        # pyqtgraph's "peak" downsampling reduces each bin of `ds` raw
        # samples to a plain min()/max() pair -- which, like numpy, propagates
        # NaN: a bin that mixes real values with the NaN gaps typical of a
        # sparse/rarely-updated field (the whole point of turning a marker on
        # -- to see individual discrete samples) collapses to NaN and draws
        # nothing at all. That only happens once zoomed out far enough for a
        # bin to span both a real value and its gaps, so the symptom is
        # exactly "invisible until zoomed in enough". A marker is the user's
        # explicit "show me every point" signal, so downsampling is switched
        # off whenever one is set; dense continuous series without a marker
        # keep the performance benefit.
        curve.setDownsampling(auto=not series.marker, method="peak")
