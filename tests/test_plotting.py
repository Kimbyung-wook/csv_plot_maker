import numpy as np

from csv_plot_maker.models.series import Series
from csv_plot_maker.plotting.plot_grid_widget import PlotGridWidget


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


def test_plot_grid_widget_rebuild_changes_dimensions(qtbot):
    widget = PlotGridWidget()
    qtbot.addWidget(widget)

    widget.rebuild(2, 2)

    for r in range(2):
        for c in range(2):
            assert widget.get_view(r, c) is not None
