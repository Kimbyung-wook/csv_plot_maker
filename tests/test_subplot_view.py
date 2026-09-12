import numpy as np

from csv_plot_maker.models.series import Series
from csv_plot_maker.plotting.plot_grid_widget import PlotGridWidget
from csv_plot_maker.plotting.subplot_view import _DEFAULT_GRID_ALPHA


def test_subplot_view_teardown_removes_right_vb_from_scene(qtbot):
    widget = PlotGridWidget()
    qtbot.addWidget(widget)
    view = widget.get_view(0, 0)

    series = Series(y_column="a", color="#1f77b4", line_style="solid", width=1.5, axis="secondary")
    view.set_series_data(series, np.array([0.0, 1.0]), np.array([1.0, 2.0]))
    assert view.right_vb.scene() is not None

    view.teardown()

    assert view.right_vb.scene() is None


def test_subplot_view_teardown_is_idempotent(qtbot):
    """teardown() must tolerate being called twice without raising: a second
    call used to hit RuntimeError from setXLink(None)/sigResized.disconnect()
    against an already-unlinked/-disconnected ViewBox (see SubplotView.
    teardown's docstring for the shiboken lifecycle bug this guards against).
    """
    widget = PlotGridWidget()
    qtbot.addWidget(widget)
    view = widget.get_view(0, 0)

    view.teardown()
    view.teardown()


def test_current_grid_alpha_falls_back_when_pyqtgraph_internal_is_missing(qtbot):
    """plot_item.ctrl.gridAlphaSlider is an undocumented pyqtgraph internal
    (see _current_grid_alpha's docstring) -- reading it must degrade to this
    app's own default instead of raising if a future pyqtgraph version
    renames or removes it.
    """
    widget = PlotGridWidget()
    qtbot.addWidget(widget)
    view = widget.get_view(0, 0)

    assert view._current_grid_alpha() == view.plot_item.ctrl.gridAlphaSlider.value()

    del view.plot_item.ctrl.gridAlphaSlider

    assert view._current_grid_alpha() == _DEFAULT_GRID_ALPHA
