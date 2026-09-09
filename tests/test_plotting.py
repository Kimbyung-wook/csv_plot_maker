import numpy as np

from csv_plot_maker.models.series import Series
from csv_plot_maker.plotting.plot_grid_widget import PlotGridWidget
from csv_plot_maker.plotting.subplot_view import _legend_sample_size


def test_plot_grid_widget_default_1x1(qtbot):
    widget = PlotGridWidget()
    qtbot.addWidget(widget)

    assert widget.get_view(0, 0) is not None


def test_subplot_view_set_and_restyle_series(qtbot):
    widget = PlotGridWidget()
    qtbot.addWidget(widget)
    view = widget.get_view(0, 0)

    series = Series(y_column="a", color="#1f77b4", line_style="solid", width=1.5)
    x = np.array([0.0, 1.0, 2.0])
    y = np.array([1.0, 2.5, 3.0])

    view.set_series_data(series, x, y)
    curve = view._curves[series.id]
    xd, yd = curve.getData()
    assert list(xd) == [0.0, 1.0, 2.0]
    assert list(yd) == [1.0, 2.5, 3.0]

    # style-only change must not touch the underlying data
    series.color = "#ff0000"
    series.line_style = "dash"
    view.update_series_style(series)
    xd2, yd2 = curve.getData()
    assert list(xd2) == list(xd)
    assert list(yd2) == list(yd)

    view.remove_series(series.id)
    assert series.id not in view._curves


def test_marker_disables_auto_downsampling(qtbot):
    # pyqtgraph's peak downsampling reduces each bin to a plain min()/max(),
    # which propagates NaN across the whole bin whenever it mixes a real
    # value with the gaps typical of a sparse series -- exactly the kind of
    # data a marker is meant to make visible. A marker must therefore switch
    # auto-downsampling off so every real sample survives regardless of zoom.
    widget = PlotGridWidget()
    qtbot.addWidget(widget)
    view = widget.get_view(0, 0)
    x = np.array([0.0, 1.0, 2.0])
    y = np.array([1.0, 2.5, 3.0])

    plain = Series(y_column="a", color="#1f77b4", line_style="solid", width=1.5, marker=None)
    view.set_series_data(plain, x, y)
    curve = view._curves[plain.id]
    assert curve.opts["autoDownsample"] is True

    marked = Series(y_column="b", color="#1f77b4", line_style="solid", width=1.5, marker="o")
    view.set_series_data(marked, x, y)
    marked_curve = view._curves[marked.id]
    assert marked_curve.opts["autoDownsample"] is False

    # Adding a marker to an already-plotted series via the Style panel must
    # retroactively disable downsampling on its existing curve too, not just
    # at initial creation time.
    plain.marker = "o"
    view.update_series_style(plain)
    assert curve.opts["autoDownsample"] is False


def test_legend_sample_size_formula():
    assert _legend_sample_size(9) == 20  # Medium: pyqtgraph's own default, unchanged
    assert _legend_sample_size(11) == 20  # Large: clamped, never exceeds the default
    assert _legend_sample_size(7) < 20  # Small
    assert _legend_sample_size(5) < _legend_sample_size(7)  # Tiny: smaller still


def test_legend_sample_icon_shrinks_below_medium_font_size(qtbot):
    # pyqtgraph's legend icon (the color-swatch/line sample) is a fixed
    # 20x20px regardless of label font size -- below Medium (9pt) that fixed
    # icon becomes taller than the shrinking text next to it, so it alone
    # pins each legend row's height and further shrinking the font stops
    # shrinking the row spacing. The icon must shrink too, once text no
    # longer needs a full 20px.
    widget = PlotGridWidget()
    qtbot.addWidget(widget)
    view = widget.get_view(0, 0)
    series = Series(y_column="a", color="#1f77b4")
    view.set_series_data(series, np.array([0.0, 1.0]), np.array([1.0, 2.0]))
    sample = view.plot_item.legend.items[0][0]

    view.set_legend_font_size(9)
    assert sample._size == 20  # Medium: unchanged from pyqtgraph's own default

    view.set_legend_font_size(11)
    assert sample._size == 20  # Large: never grows past the original default

    view.set_legend_font_size(5)
    assert sample._size == _legend_sample_size(5)
    assert sample._size < 20  # Tiny: now actually shrinks


def test_legend_sample_icon_size_applies_to_curves_added_after_a_size_change(qtbot):
    # The icon size for a *newly* added curve comes from a class-level
    # default (see _ScalableItemSample) rather than being passed through
    # pyqtgraph's own LegendItem.addItem(), since that always constructs a
    # sample as `sampleType(item)` with no size argument -- a curve added
    # after switching to Tiny must not default back to the 20px icon.
    widget = PlotGridWidget()
    qtbot.addWidget(widget)
    view = widget.get_view(0, 0)
    view.set_legend_font_size(5)

    series = Series(y_column="a", color="#1f77b4")
    view.set_series_data(series, np.array([0.0, 1.0]), np.array([1.0, 2.0]))

    sample = view.plot_item.legend.items[0][0]
    assert sample._size == _legend_sample_size(5)


def test_plot_grid_widget_rebuild_changes_dimensions(qtbot):
    widget = PlotGridWidget()
    qtbot.addWidget(widget)

    widget.rebuild(2, 2)

    for r in range(2):
        for c in range(2):
            assert widget.get_view(r, c) is not None


def test_subplot_view_teardown_removes_right_vb_from_scene(qtbot):
    widget = PlotGridWidget()
    qtbot.addWidget(widget)
    view = widget.get_view(0, 0)

    series = Series(y_column="a", color="#1f77b4", line_style="solid", width=1.5, axis="secondary")
    view.set_series_data(series, np.array([0.0, 1.0]), np.array([1.0, 2.0]))
    assert view.right_vb.scene() is not None

    view.teardown()

    assert view.right_vb.scene() is None


def test_plot_grid_widget_rebuild_clears_previous_secondary_viewboxes(qtbot):
    """Regression test for the "잔상"/ghost-trace bug: a secondary-axis
    ViewBox is added directly to the scene (see SubplotView.__init__) rather
    than parented under its PlotItem, so a naive rebuild -- which only
    removes PlotItems from the scene -- used to leave it (and any curves
    still attached to it) behind permanently, stranded but still rendered.
    """
    widget = PlotGridWidget()
    qtbot.addWidget(widget)
    view = widget.get_view(0, 0)
    series = Series(y_column="a", color="#1f77b4", line_style="solid", width=1.5, axis="secondary")
    view.set_series_data(series, np.array([0.0, 1.0]), np.array([1.0, 2.0]))
    stale_right_vb = view.right_vb

    widget.rebuild(2, 2)

    assert stale_right_vb.scene() is None
