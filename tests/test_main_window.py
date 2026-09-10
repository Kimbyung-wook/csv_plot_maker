import numpy as np

from csv_plot_maker.data.column_store import ColumnStore
from csv_plot_maker.models.serialization import save_project
from csv_plot_maker.models.series import Series
from csv_plot_maker.ui.main_window import MainWindow


def _store_with(sparse_col: np.ndarray, dense_col: np.ndarray) -> ColumnStore:
    store = ColumnStore(row_count=len(sparse_col))
    store.columns["sparse"] = sparse_col
    store.numeric["sparse"] = True
    store.columns["dense"] = dense_col
    store.numeric["dense"] = True
    return store


def test_dropping_a_sparse_column_defaults_to_dot_marker_and_no_line(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.column_store = _store_with(
        sparse_col=np.array([np.nan, np.nan, np.nan, 1.0]),
        dense_col=np.array([1.0, 2.0, 3.0, 4.0]),
    )
    subplot = win._active_subplot()

    win._on_column_dropped(subplot.row, subplot.col, "sparse")

    series = subplot.series[-1]
    assert series.marker == "dot"
    assert series.line_style == "none"


def test_apply_x_to_all_copies_active_subplots_x_column_and_offset(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.column_store = _store_with(
        sparse_col=np.array([np.nan, 1.0]),
        dense_col=np.array([1.0, 2.0]),
    )
    win.project.resize_grid(1, 2)
    win.plot_grid.rebuild(1, 2)

    active = win._active_subplot()
    active.x_column = "dense"
    active.x_offset = 5.0
    other = next(sp for sp in win.project.subplots if sp.id != active.id)
    other.x_column = "sparse"
    other.x_offset = -1.0

    win._on_apply_x_to_all_requested()

    for sp in win.project.subplots:
        assert sp.x_column == "dense"
        assert sp.x_offset == 5.0


def test_transform_changed_applies_scale_and_offset_to_the_selected_series(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.column_store = _store_with(
        sparse_col=np.array([np.nan, 1.0]),
        dense_col=np.array([1.0, 2.0, 3.0, 4.0]),
    )
    subplot = win._active_subplot()
    subplot.x_column = "dense"
    win._on_column_dropped(subplot.row, subplot.col, "dense")
    series = subplot.series[-1]
    win._on_series_selection_changed(series.id)

    win.style_panel.scale_spin.setValue(2.0)
    win.style_panel.offset_spin.setValue(-1.0)

    assert series.scale == 2.0
    assert series.offset == -1.0
    curve = win._active_view()._curves[series.id]
    _xd, yd = curve.getData()
    assert list(yd) == [1.0, 3.0, 5.0, 7.0]  # dense * 2 - 1


def test_dropping_a_dense_column_keeps_default_solid_line_and_no_marker(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.column_store = _store_with(
        sparse_col=np.array([np.nan, np.nan, np.nan, 1.0]),
        dense_col=np.array([1.0, 2.0, 3.0, 4.0]),
    )
    subplot = win._active_subplot()

    win._on_column_dropped(subplot.row, subplot.col, "dense")

    series = subplot.series[-1]
    assert series.marker is None
    assert series.line_style == "solid"


def test_dropping_a_column_already_in_the_active_subplot_moves_it_to_the_target(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.column_store = _store_with(
        sparse_col=np.array([np.nan, 1.0]),
        dense_col=np.array([1.0, 2.0]),
    )
    win.project.resize_grid(1, 2)
    win.plot_grid.rebuild(1, 2)

    source = win._active_subplot()
    target = next(sp for sp in win.project.subplots if sp.id != source.id)
    win._on_column_dropped(source.row, source.col, "dense")
    assert [s.y_column for s in source.series] == ["dense"]
    original_series = source.series[0]
    original_series.color = "#abcdef"
    original_series.axis = "secondary"

    win._on_column_dropped(target.row, target.col, "dense")

    assert [s.y_column for s in source.series] == []
    assert [s.y_column for s in target.series] == ["dense"]
    assert win._active_subplot().id == target.id
    # The exact same Series object moves over -- a move must not reset a
    # style/axis the user already set on it back to defaults.
    moved_series = target.series[0]
    assert moved_series.id == original_series.id
    assert moved_series.color == "#abcdef"
    assert moved_series.axis == "secondary"


def test_dropping_a_column_back_onto_its_own_subplot_still_allows_a_duplicate(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.column_store = _store_with(
        sparse_col=np.array([np.nan, 1.0]),
        dense_col=np.array([1.0, 2.0]),
    )
    subplot = win._active_subplot()
    win._on_column_dropped(subplot.row, subplot.col, "dense")

    win._on_column_dropped(subplot.row, subplot.col, "dense")

    assert [s.y_column for s in subplot.series] == ["dense", "dense"]


def test_dropping_a_column_present_in_multiple_subplots_is_left_ambiguous_and_not_moved(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.column_store = _store_with(
        sparse_col=np.array([np.nan, 1.0]),
        dense_col=np.array([1.0, 2.0]),
    )
    win.project.resize_grid(1, 3)
    win.plot_grid.rebuild(1, 3)
    first, second, third = win.project.subplots
    # Added directly (bypassing the drop handler) so both already hold
    # "dense" independently of each other, rather than the second drop
    # itself moving the first's copy over -- that's the single-match "move"
    # case covered by the test above, not what's under test here.
    first.add_series(Series(y_column="dense"))
    second.add_series(Series(y_column="dense"))

    win._on_column_dropped(third.row, third.col, "dense")

    assert [s.y_column for s in first.series] == ["dense"]
    assert [s.y_column for s in second.series] == ["dense"]
    assert [s.y_column for s in third.series] == ["dense"]


def test_choosing_a_legend_font_size_updates_project_and_plot_grid(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)

    win._on_legend_font_size_changed(11)

    assert win.project.legend_font_size == 11
    assert win.plot_grid._legend_font_pt == 11
    assert win._legend_font_actions[11].isChecked()
    assert not win._legend_font_actions[9].isChecked()


def test_loading_a_layout_restores_its_saved_legend_font_size(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    win.column_store = _store_with(
        sparse_col=np.array([np.nan, 1.0]),
        dense_col=np.array([1.0, 2.0]),
    )
    saved = win.project
    saved.legend_font_size = 7
    path = tmp_path / "layout.json"
    save_project(saved, str(path))
    # Change it away from the saved value first so the assertion below can't
    # pass by coincidence (e.g. both happening to already be the default).
    win._on_legend_font_size_changed(11)

    win._load_layout_from_path(str(path))

    assert win.project.legend_font_size == 7
    assert win.plot_grid._legend_font_pt == 7
    assert win._legend_font_actions[7].isChecked()


def _two_row_grid_with_shared_columns(qtbot) -> MainWindow:
    win = MainWindow()
    qtbot.addWidget(win)
    win.column_store = _store_with(
        sparse_col=np.array([1.0, 2.0]),
        dense_col=np.array([1.0, 2.0]),
    )
    win.project.resize_grid(2, 1)
    win.plot_grid.rebuild(2, 1)
    for sp in win.project.subplots:
        sp.x_column = "dense"
    return win


def test_non_bottom_row_title_is_blanked_when_every_subplot_shares_x(qtbot):
    win = _two_row_grid_with_shared_columns(qtbot)
    top = next(sp for sp in win.project.subplots if sp.row == 0)
    bottom = next(sp for sp in win.project.subplots if sp.row == 1)

    win._replot_all_subplots()

    assert win._shared_x_axis() is True
    assert win._effective_x_label(top) == ""
    assert win._effective_x_label(bottom) == "dense"
    top_axis = win.plot_grid.get_view(top.row, top.col).plot_item.getAxis("bottom")
    bottom_axis = win.plot_grid.get_view(bottom.row, bottom.col).plot_item.getAxis("bottom")
    assert top_axis.label.isVisible() is False
    assert bottom_axis.label.isVisible() is True


def test_every_row_keeps_its_title_when_x_columns_differ(qtbot):
    win = _two_row_grid_with_shared_columns(qtbot)
    top = next(sp for sp in win.project.subplots if sp.row == 0)
    bottom = next(sp for sp in win.project.subplots if sp.row == 1)
    top.x_column = "sparse"

    win._replot_all_subplots()

    assert win._shared_x_axis() is False
    assert win._effective_x_label(top) == "sparse"
    assert win._effective_x_label(bottom) == "dense"


def test_shared_x_axis_requires_matching_offset_too(qtbot):
    win = _two_row_grid_with_shared_columns(qtbot)
    top = next(sp for sp in win.project.subplots if sp.row == 0)
    top.x_offset = 5.0

    assert win._shared_x_axis() is False
    assert win._effective_x_label(top) == "dense"


def test_titles_come_back_once_columns_diverge_again_after_being_shared(qtbot):
    win = _two_row_grid_with_shared_columns(qtbot)
    top = next(sp for sp in win.project.subplots if sp.row == 0)
    bottom = next(sp for sp in win.project.subplots if sp.row == 1)
    win._replot_all_subplots()
    top_axis = win.plot_grid.get_view(top.row, top.col).plot_item.getAxis("bottom")
    assert top_axis.label.isVisible() is False

    top.x_column = "sparse"
    win._replot_subplot(top)

    assert top_axis.label.isVisible() is True
    bottom_axis = win.plot_grid.get_view(bottom.row, bottom.col).plot_item.getAxis("bottom")
    assert bottom_axis.label.isVisible() is True


def test_capture_current_y_ranges_reads_primary_and_secondary_ranges(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.column_store = _store_with(
        sparse_col=np.array([1.0, 2.0]),
        dense_col=np.array([10.0, 20.0]),
    )
    win.column_store.columns["extra"] = np.array([100.0, 200.0])
    win.column_store.numeric["extra"] = True
    subplot = win._active_subplot()
    subplot.x_column = "dense"
    subplot.add_series(Series(y_column="sparse", axis="primary"))
    subplot.add_series(Series(y_column="extra", axis="secondary"))
    win._replot_subplot(subplot)
    view = win.plot_grid.get_view(subplot.row, subplot.col)
    view.plot_item.setYRange(-1, 1, padding=0)
    view.right_vb.setYRange(-100, 100, padding=0)

    win._capture_current_y_ranges()

    assert subplot.y_range_left == [-1.0, 1.0]
    assert subplot.y_range_right == [-100.0, 100.0]


def test_capture_current_y_ranges_clears_stale_values_on_empty_subplots(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    subplot = win._active_subplot()
    subplot.y_range_left = [1.0, 2.0]
    subplot.y_range_right = [3.0, 4.0]

    win._capture_current_y_ranges()

    assert subplot.y_range_left is None
    assert subplot.y_range_right is None


def test_restore_saved_y_ranges_overrides_a_fresh_autorange(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.column_store = _store_with(
        sparse_col=np.array([1.0, 2.0]),
        dense_col=np.array([10.0, 20.0]),
    )
    subplot = win._active_subplot()
    subplot.x_column = "dense"
    subplot.add_series(Series(y_column="sparse"))
    subplot.y_range_left = [-1.0, 1.0]
    win._replot_subplot(subplot)
    win._autorange_all_views()
    view = win.plot_grid.get_view(subplot.row, subplot.col)
    assert view.plot_item.vb.viewRange()[1] != [-1.0, 1.0]

    win._restore_saved_y_ranges()

    assert view.plot_item.vb.viewRange()[1] == [-1.0, 1.0]


def test_saved_y_range_round_trips_through_load_layout(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    win.column_store = _store_with(
        sparse_col=np.array([1.0, 2.0]),
        dense_col=np.array([10.0, 20.0]),
    )
    subplot = win._active_subplot()
    subplot.x_column = "dense"
    subplot.add_series(Series(y_column="sparse"))
    win._replot_subplot(subplot)
    view = win.plot_grid.get_view(subplot.row, subplot.col)
    view.plot_item.setYRange(-7.0, 7.0, padding=0)
    win._capture_current_y_ranges()
    path = tmp_path / "layout.json"
    save_project(win.project, str(path))

    win._load_layout_from_path(str(path))

    loaded_subplot = win._active_subplot()
    assert loaded_subplot.y_range_left == [-7.0, 7.0]
    view_after = win.plot_grid.get_view(loaded_subplot.row, loaded_subplot.col)
    assert view_after.plot_item.vb.viewRange()[1] == [-7.0, 7.0]


def test_legend_font_size_menu_includes_a_tiny_option(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)

    win._on_legend_font_size_changed(5)

    assert win.project.legend_font_size == 5
    assert win.plot_grid._legend_font_pt == 5
    assert win._legend_font_actions[5].isChecked()
