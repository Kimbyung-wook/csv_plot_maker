from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt

from csv_plot_maker.data.column_store import ColumnStore
from csv_plot_maker.models.data_source import DataSource, SourceRef
from csv_plot_maker.models.serialization import save_project
from csv_plot_maker.models.series import Series
from csv_plot_maker.ui.main_window import MainWindow

FIXTURE = Path(__file__).parent / "fixtures" / "small.csv"


def _store_with(sparse_col: np.ndarray, dense_col: np.ndarray) -> ColumnStore:
    store = ColumnStore(row_count=len(sparse_col))
    # Every real load_csv() result always has this synthetic fallback X
    # column (see loader.py) -- included here so code that defaults a blank
    # subplot's X to "Sequential" (there's no "timestamp" in this fixture)
    # finds real data behind it, same as it would for an actual loaded file.
    store.columns["Sequential"] = np.arange(1, len(sparse_col) + 1, dtype=np.float64)
    store.numeric["Sequential"] = True
    store.columns["sparse"] = sparse_col
    store.numeric["sparse"] = True
    store.columns["dense"] = dense_col
    store.numeric["dense"] = True
    return store


def _install_store(win: MainWindow, store: ColumnStore, source_id: str = "src") -> DataSource:
    source = DataSource(id=source_id, path=f"{source_id}.csv", label=source_id, color="#dbeafe", store=store)
    win.data_sources[source_id] = source
    return source


def test_dropping_a_sparse_column_defaults_to_dot_marker_and_no_line(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source = _install_store(
        win,
        _store_with(
            sparse_col=np.array([np.nan, np.nan, np.nan, 1.0]),
            dense_col=np.array([1.0, 2.0, 3.0, 4.0]),
        ),
    )
    subplot = win._active_subplot()

    win._on_column_dropped(subplot.row, subplot.col, source.id, "sparse")

    series = subplot.series[-1]
    assert series.marker == "dot"
    assert series.line_style == "none"


def test_apply_x_to_matching_series_copies_to_other_series_from_the_same_file(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source_a = _install_store(
        win, _store_with(sparse_col=np.array([np.nan, 1.0]), dense_col=np.array([1.0, 2.0])), "a"
    )
    source_b = _install_store(
        win, _store_with(sparse_col=np.array([np.nan, 1.0]), dense_col=np.array([10.0, 20.0])), "b"
    )
    win.project.resize_grid(1, 2)
    win.plot_grid.rebuild(1, 2)
    sp0, sp1 = win.project.subplots
    win._on_column_dropped(sp0.row, sp0.col, source_a.id, "dense")
    win._on_column_dropped(sp0.row, sp0.col, source_a.id, "sparse")
    win._on_column_dropped(sp1.row, sp1.col, source_b.id, "dense")
    edited, sibling = sp0.series
    other_file_series = sp1.series[0]
    win._set_active_subplot(sp0.id)
    win._on_series_selection_changed(edited.id)
    edited.x_column = "sparse"
    edited.x_offset = 5.0

    win._on_apply_x_to_matching_series_requested()

    assert sibling.x_column == "sparse"
    assert sibling.x_offset == 5.0
    # A series from a different file is untouched -- "this file" scopes the
    # bulk apply, since X must always come from the same file as its own Y.
    assert other_file_series.x_column == "Sequential"
    assert other_file_series.x_offset == 0.0


def test_transform_changed_applies_scale_and_offset_to_the_selected_series(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source = _install_store(
        win,
        _store_with(
            sparse_col=np.array([np.nan, 1.0, 2.0, 3.0]),
            dense_col=np.array([1.0, 2.0, 3.0, 4.0]),
        ),
    )
    subplot = win._active_subplot()
    win._on_column_dropped(subplot.row, subplot.col, source.id, "dense")
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
    source = _install_store(
        win,
        _store_with(
            sparse_col=np.array([np.nan, np.nan, np.nan, 1.0]),
            dense_col=np.array([1.0, 2.0, 3.0, 4.0]),
        ),
    )
    subplot = win._active_subplot()

    win._on_column_dropped(subplot.row, subplot.col, source.id, "dense")

    series = subplot.series[-1]
    assert series.marker is None
    assert series.line_style == "solid"


def test_dropping_a_column_already_in_the_active_subplot_moves_it_to_the_target(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source = _install_store(
        win,
        _store_with(
            sparse_col=np.array([np.nan, 1.0]),
            dense_col=np.array([1.0, 2.0]),
        ),
    )
    win.project.resize_grid(1, 2)
    win.plot_grid.rebuild(1, 2)

    source_subplot = win._active_subplot()
    target = next(sp for sp in win.project.subplots if sp.id != source_subplot.id)
    win._on_column_dropped(source_subplot.row, source_subplot.col, source.id, "dense")
    assert [s.y_column for s in source_subplot.series] == ["dense"]
    original_series = source_subplot.series[0]
    original_series.color = "#abcdef"
    original_series.axis = "secondary"

    win._on_column_dropped(target.row, target.col, source.id, "dense")

    assert [s.y_column for s in source_subplot.series] == []
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
    source = _install_store(
        win,
        _store_with(
            sparse_col=np.array([np.nan, 1.0]),
            dense_col=np.array([1.0, 2.0]),
        ),
    )
    subplot = win._active_subplot()
    win._on_column_dropped(subplot.row, subplot.col, source.id, "dense")

    win._on_column_dropped(subplot.row, subplot.col, source.id, "dense")

    assert [s.y_column for s in subplot.series] == ["dense", "dense"]


def test_dropping_a_column_present_in_multiple_subplots_is_left_ambiguous_and_not_moved(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source = _install_store(
        win,
        _store_with(
            sparse_col=np.array([np.nan, 1.0]),
            dense_col=np.array([1.0, 2.0]),
        ),
    )
    win.project.resize_grid(1, 3)
    win.plot_grid.rebuild(1, 3)
    first, second, third = win.project.subplots
    # Added directly (bypassing the drop handler) so both already hold
    # "dense" independently of each other, rather than the second drop
    # itself moving the first's copy over -- that's the single-match "move"
    # case covered by the test above, not what's under test here.
    first.add_series(Series(y_column="dense", source_id=source.id))
    second.add_series(Series(y_column="dense", source_id=source.id))

    win._on_column_dropped(third.row, third.col, source.id, "dense")

    assert [s.y_column for s in first.series] == ["dense"]
    assert [s.y_column for s in second.series] == ["dense"]
    assert [s.y_column for s in third.series] == ["dense"]


def test_dropping_columns_from_two_different_files_into_the_same_subplot_both_survive(qtbot):
    # X is a per-series property (see Series.x_column), so a subplot mixing
    # files is expected -- each series just gets its own file's default X
    # rather than one being rejected or bumping the other's X.
    win = MainWindow()
    qtbot.addWidget(win)
    source_a = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([1.0, 2.0])), "a")
    source_b = _install_store(
        win, _store_with(np.array([np.nan, 1.0, 2.0]), np.array([10.0, 20.0, 30.0])), "b"
    )
    subplot = win._active_subplot()

    win._on_column_dropped(subplot.row, subplot.col, source_a.id, "dense")
    win._on_column_dropped(subplot.row, subplot.col, source_b.id, "dense")

    assert [(s.source_id, s.y_column) for s in subplot.series] == [
        (source_a.id, "dense"),
        (source_b.id, "dense"),
    ]
    # Neither fixture has a "timestamp" column, so both fall back to
    # "Sequential" -- but each from its own file.
    assert all(s.x_column == "Sequential" for s in subplot.series)


def test_series_from_two_files_in_one_subplot_each_render_their_own_length(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source_a = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([1.0, 2.0])), "a")
    source_b = _install_store(
        win, _store_with(np.array([np.nan, 1.0, 2.0]), np.array([10.0, 20.0, 30.0])), "b"
    )
    subplot = win._active_subplot()
    win._on_column_dropped(subplot.row, subplot.col, source_a.id, "dense")
    win._on_column_dropped(subplot.row, subplot.col, source_b.id, "dense")

    win._replot_subplot(subplot)

    view = win.plot_grid.get_view(subplot.row, subplot.col)
    series_a, series_b = subplot.series
    xa, ya = view._curves[series_a.id].getData()
    xb, yb = view._curves[series_b.id].getData()
    assert len(xa) == len(ya) == 2
    assert len(xb) == len(yb) == 3
    assert list(ya) == [1.0, 2.0]
    assert list(yb) == [10.0, 20.0, 30.0]


def test_moving_a_series_to_another_subplot_keeps_its_own_x_column_and_offset(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source = _install_store(
        win, _store_with(sparse_col=np.array([np.nan, 1.0]), dense_col=np.array([1.0, 2.0])), "a"
    )
    win.project.resize_grid(1, 2)
    win.plot_grid.rebuild(1, 2)
    origin = win._active_subplot()
    target = next(sp for sp in win.project.subplots if sp.id != origin.id)
    win._on_column_dropped(origin.row, origin.col, source.id, "dense")
    origin.series[0].x_column = "sparse"
    origin.series[0].x_offset = 3.0

    win._on_column_dropped(target.row, target.col, source.id, "dense")

    assert origin.series == []
    moved = target.series[0]
    assert moved.x_column == "sparse"
    assert moved.x_offset == 3.0


def test_prune_invalid_references_drops_series_whose_x_column_no_longer_exists(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([1.0, 2.0])), "a")
    subplot = win._active_subplot()
    subplot.add_series(Series(y_column="dense", source_id=source.id, x_column="missing_column"))
    subplot.add_series(Series(y_column="dense", source_id=source.id, x_column="Sequential"))

    dropped = win._prune_invalid_references()

    assert dropped == 1
    assert [s.x_column for s in subplot.series] == ["Sequential"]


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
    _install_store(
        win,
        _store_with(
            sparse_col=np.array([np.nan, 1.0]),
            dense_col=np.array([1.0, 2.0]),
        ),
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
    source = _install_store(
        win,
        _store_with(
            sparse_col=np.array([1.0, 2.0]),
            dense_col=np.array([1.0, 2.0]),
        ),
    )
    win.project.resize_grid(2, 1)
    win.plot_grid.rebuild(2, 1)
    for sp in win.project.subplots:
        sp.add_series(Series(y_column="sparse", source_id=source.id, x_column="dense"))
    return win


def test_non_bottom_row_title_is_blanked_when_every_subplot_shares_x(qtbot):
    win = _two_row_grid_with_shared_columns(qtbot)
    top = next(sp for sp in win.project.subplots if sp.row == 0)
    bottom = next(sp for sp in win.project.subplots if sp.row == 1)

    win._replot_all_subplots()

    assert win.project.has_shared_x_axis() is True
    assert win.project.effective_x_label(top) == ""
    assert win.project.effective_x_label(bottom) == "dense"
    top_axis = win.plot_grid.get_view(top.row, top.col).plot_item.getAxis("bottom")
    bottom_axis = win.plot_grid.get_view(bottom.row, bottom.col).plot_item.getAxis("bottom")
    assert top_axis.label.isVisible() is False
    assert bottom_axis.label.isVisible() is True


def test_every_row_keeps_its_title_when_x_columns_differ(qtbot):
    win = _two_row_grid_with_shared_columns(qtbot)
    top = next(sp for sp in win.project.subplots if sp.row == 0)
    bottom = next(sp for sp in win.project.subplots if sp.row == 1)
    top.series[0].x_column = "sparse"

    win._replot_all_subplots()

    assert win.project.has_shared_x_axis() is False
    assert win.project.effective_x_label(top) == "sparse"
    assert win.project.effective_x_label(bottom) == "dense"


def test_shared_x_axis_requires_matching_offset_too(qtbot):
    win = _two_row_grid_with_shared_columns(qtbot)
    top = next(sp for sp in win.project.subplots if sp.row == 0)
    top.series[0].x_offset = 5.0

    assert win.project.has_shared_x_axis() is False
    assert win.project.effective_x_label(top) == "dense"


def test_shared_x_axis_requires_matching_source_too(qtbot):
    # Same column *name* from two different files is not the same X data --
    # has_shared_x_axis must not collapse titles just because the names match.
    win = _two_row_grid_with_shared_columns(qtbot)
    other_store = _store_with(
        sparse_col=np.array([1.0, 2.0]),
        dense_col=np.array([100.0, 200.0]),
    )
    other_source = _install_store(win, other_store, source_id="other")
    top = next(sp for sp in win.project.subplots if sp.row == 0)
    top.series[0].source_id = other_source.id

    assert win.project.has_shared_x_axis() is False
    assert win.project.effective_x_label(top) == "dense"


def test_titles_come_back_once_columns_diverge_again_after_being_shared(qtbot):
    win = _two_row_grid_with_shared_columns(qtbot)
    top = next(sp for sp in win.project.subplots if sp.row == 0)
    bottom = next(sp for sp in win.project.subplots if sp.row == 1)
    win._replot_all_subplots()
    top_axis = win.plot_grid.get_view(top.row, top.col).plot_item.getAxis("bottom")
    assert top_axis.label.isVisible() is False

    top.series[0].x_column = "sparse"
    win._replot_subplot(top)

    assert top_axis.label.isVisible() is True
    bottom_axis = win.plot_grid.get_view(bottom.row, bottom.col).plot_item.getAxis("bottom")
    assert bottom_axis.label.isVisible() is True


def test_capture_current_y_ranges_reads_primary_and_secondary_ranges(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source = _install_store(
        win,
        _store_with(
            sparse_col=np.array([1.0, 2.0]),
            dense_col=np.array([10.0, 20.0]),
        ),
    )
    source.store.columns["extra"] = np.array([100.0, 200.0])
    source.store.numeric["extra"] = True
    subplot = win._active_subplot()
    subplot.add_series(Series(y_column="sparse", source_id=source.id, x_column="dense", axis="primary"))
    subplot.add_series(Series(y_column="extra", source_id=source.id, x_column="dense", axis="secondary"))
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
    source = _install_store(
        win,
        _store_with(
            sparse_col=np.array([1.0, 2.0]),
            dense_col=np.array([10.0, 20.0]),
        ),
    )
    subplot = win._active_subplot()
    subplot.add_series(Series(y_column="sparse", source_id=source.id, x_column="dense"))
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
    source = _install_store(
        win,
        _store_with(
            sparse_col=np.array([1.0, 2.0]),
            dense_col=np.array([10.0, 20.0]),
        ),
    )
    subplot = win._active_subplot()
    subplot.add_series(Series(y_column="sparse", source_id=source.id, x_column="dense"))
    win._replot_subplot(subplot)
    view = win.plot_grid.get_view(subplot.row, subplot.col)
    view.plot_item.setYRange(-7.0, 7.0, padding=0)
    win._capture_current_y_ranges()
    win._capture_data_source_refs()
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


def test_source_column_options_returns_only_that_sources_own_columns(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source_a = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([1.0, 2.0])), "a")
    _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([10.0, 20.0])), "b")

    options = win._source_column_options(source_a.id)

    assert set(options) == {"Sequential", "sparse", "dense"}


def test_source_column_options_is_empty_for_a_source_still_loading(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.data_sources["a"] = DataSource(id="a", path="a.csv", label="a", color="#dbeafe", store=None)

    assert win._source_column_options("a") == []


def test_series_list_has_no_color_tint_with_only_one_csv_open(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([1.0, 2.0])), "a")
    subplot = win._active_subplot()
    subplot.add_series(Series(y_column="dense", source_id=source.id))

    win._refresh_series_list()

    assert win.series_panel.series_list.item(0).background().style() == Qt.BrushStyle.NoBrush


def test_series_list_shows_color_tint_once_a_second_csv_is_open(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source_a = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([1.0, 2.0])), "a")
    _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([10.0, 20.0])), "b")
    subplot = win._active_subplot()
    subplot.add_series(Series(y_column="dense", source_id=source_a.id))

    win._refresh_series_list()

    assert win.series_panel.series_list.item(0).background().style() != Qt.BrushStyle.NoBrush


def test_on_source_renamed_refreshes_the_legend_prefix_for_mixed_subplots(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source_a = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([1.0, 2.0])), "a")
    source_b = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([10.0, 20.0])), "b")
    subplot = win._active_subplot()
    subplot.add_series(Series(y_column="dense", source_id=source_a.id, x_column="Sequential"))
    subplot.add_series(Series(y_column="dense", source_id=source_b.id, x_column="Sequential"))
    win._replot_subplot(subplot)
    view = win.plot_grid.get_view(subplot.row, subplot.col)
    legend_texts_before = [label.text for _sample, label in view.plot_item.legend.items]
    assert any(t.startswith("a:") for t in legend_texts_before)

    source_a.label = "renamed-a"
    win._on_source_renamed(source_a.id)

    legend_texts_after = [label.text for _sample, label in view.plot_item.legend.items]
    assert any(t.startswith("renamed-a:") for t in legend_texts_after)
    assert not any(t.startswith("a:") for t in legend_texts_after)


def test_only_linked_subplots_share_x_range_the_rest_stay_independent(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source = _install_store(
        win,
        _store_with(
            sparse_col=np.array([1.0, 2.0, 3.0]),
            dense_col=np.array([1.0, 2.0, 3.0]),
        ),
    )
    win.project.resize_grid(1, 3)
    win.plot_grid.rebuild(1, 3)
    linked_a, linked_b, independent = win.project.subplots
    for sp in win.project.subplots:
        sp.add_series(Series(y_column="sparse", source_id=source.id, x_column="dense"))
    win._replot_all_subplots()
    win._set_active_subplot(linked_a.id)
    win._on_subplot_link_x_toggled(True)
    win._set_active_subplot(linked_b.id)
    win._on_subplot_link_x_toggled(True)

    view_a = win.plot_grid.get_view(linked_a.row, linked_a.col)
    view_b = win.plot_grid.get_view(linked_b.row, linked_b.col)
    view_c = win.plot_grid.get_view(independent.row, independent.col)
    original_c_range = list(view_c.plot_item.vb.viewRange()[0])

    view_a.plot_item.setXRange(10.0, 20.0, padding=0)

    assert list(view_b.plot_item.vb.viewRange()[0]) == [10.0, 20.0]
    assert list(view_c.plot_item.vb.viewRange()[0]) == original_c_range


def test_grid_dims_changed_preserves_x_range_of_populated_subplots(qtbot):
    """_on_grid_dims_changed's rebuild discards and recreates every
    SubplotView, wiping the user's pan/zoom back to pyqtgraph's default
    (0, 1) range -- it must snapshot each populated subplot's X range by
    (row, col) position first and reapply it once the new views exist.
    """
    win = MainWindow()
    qtbot.addWidget(win)
    source = _install_store(
        win,
        _store_with(
            sparse_col=np.array([1.0, 2.0, 3.0]),
            dense_col=np.array([1.0, 2.0, 3.0]),
        ),
    )
    win.project.resize_grid(1, 2)
    win.plot_grid.rebuild(1, 2)
    populated, empty = win.project.subplots
    populated.add_series(Series(y_column="sparse", source_id=source.id, x_column="dense"))
    win._replot_all_subplots()

    view = win.plot_grid.get_view(populated.row, populated.col)
    view.set_x_range(10.0, 20.0, padding=0)

    win._on_grid_dims_changed(1, 3)

    restored_view = win.plot_grid.get_view(populated.row, populated.col)
    assert list(restored_view.get_x_range()) == [10.0, 20.0]


def test_loading_a_second_csv_does_not_reset_existing_subplots(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source_a = DataSource(
        id="a",
        path="a.csv",
        label="a",
        color="#dbeafe",
        store=_store_with(sparse_col=np.array([np.nan, 1.0]), dense_col=np.array([1.0, 2.0])),
    )
    win._on_csv_loaded(source_a)
    win.project.resize_grid(1, 2)
    win.plot_grid.rebuild(1, 2)
    sp0 = win._active_subplot()
    win._on_column_dropped(sp0.row, sp0.col, source_a.id, "dense")
    assert len(sp0.series) == 1

    source_b = DataSource(
        id="b",
        path="b.csv",
        label="b",
        color="#dcfce7",
        store=_store_with(sparse_col=np.array([np.nan, 1.0]), dense_col=np.array([10.0, 20.0])),
    )
    win._on_csv_loaded(source_b)

    # Loading a second file appends -- it must not reset the grid/series
    # that came from the first one, the way opening the very first CSV does.
    assert win.project.grid_cols == 2
    assert len(sp0.series) == 1
    assert sp0.series[0].y_column == "dense"
    assert "a" in win.data_sources
    assert "b" in win.data_sources


def test_on_csv_closed_prunes_only_that_sources_series(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source_a = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([1.0, 2.0])), "a")
    source_b = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([10.0, 20.0])), "b")
    subplot = win._active_subplot()
    subplot.add_series(Series(y_column="dense", source_id=source_a.id, x_column="Sequential"))
    subplot.add_series(Series(y_column="dense", source_id=source_b.id, x_column="Sequential"))
    win._replot_subplot(subplot)

    win._on_csv_closed(source_b.id)

    assert [s.source_id for s in subplot.series] == [source_a.id]
    assert source_b.id not in win.data_sources
    # must not crash trying to replot the now-pruned subplot
    win._replot_subplot(subplot)


def test_on_csv_closed_removes_the_subplots_only_series_when_that_file_closes(qtbot):
    # A subplot is no longer pinned to one file (see Series.x_column) --
    # closing the file its only series came from just removes that series,
    # the same per-series pruning as when other subplots also use it.
    win = MainWindow()
    qtbot.addWidget(win)
    source_a = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([1.0, 2.0])), "a")
    subplot = win._active_subplot()
    subplot.add_series(Series(y_column="dense", source_id=source_a.id, x_column="Sequential"))
    win._replot_subplot(subplot)

    win._on_csv_closed(source_a.id)

    assert subplot.series == []


def test_on_all_files_closed_resets_to_a_blank_single_subplot_grid(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source_a = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([1.0, 2.0])), "a")
    win.project.resize_grid(1, 2)
    win.plot_grid.rebuild(1, 2)
    sp0 = win._active_subplot()
    win._on_column_dropped(sp0.row, sp0.col, source_a.id, "dense")
    assert len(sp0.series) == 1

    win._on_all_files_closed()

    assert win.data_sources == {}
    assert win.project.grid_rows == 1
    assert win.project.grid_cols == 1
    assert len(win.project.subplots) == 1
    assert win.project.subplots[0].series == []


def test_reconcile_project_data_sources_remaps_old_ids_by_matching_path(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    source_a = _install_store(win, _store_with(np.array([np.nan, 1.0]), np.array([1.0, 2.0])), "new-id")
    source_a.path = "a.csv"
    subplot = win._active_subplot()
    subplot.add_series(Series(y_column="dense", source_id="old-id", x_column="Sequential"))
    win.project.data_sources = [SourceRef(id="old-id", path="a.csv", label="a", color="#dbeafe")]

    win._reconcile_project_data_sources()

    assert subplot.series[0].source_id == "new-id"


def test_old_style_global_link_x_axes_migrates_to_every_subplot_linked(qtbot, tmp_path):
    win = MainWindow()
    qtbot.addWidget(win)
    win.project.resize_grid(1, 2)
    win.plot_grid.rebuild(1, 2)
    path = tmp_path / "layout.json"
    save_project(win.project, str(path))
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    data["link_x_axes"] = True
    for sp in data["subplots"]:
        sp.pop("link_x_axis", None)
    path.write_text(json.dumps(data), encoding="utf-8")

    win._load_layout_from_path(str(path))

    assert all(sp.link_x_axis for sp in win.project.subplots)


def test_data_source_registries_stay_in_sync_across_load_and_close(qtbot):
    """CsvPanel._sources and MainWindow.data_sources are two independently
    updated registries of the same open files (populated on different
    triggers -- load-start vs. load-finish success), kept consistent only
    by convention rather than a single owner. This is a characterization
    test for that convention rather than of one specific code path: it
    should keep failing loudly if a future change ever lets the two drift
    apart, since nothing else in the test suite would catch that.
    """
    win = MainWindow()
    qtbot.addWidget(win)

    with qtbot.waitSignal(win.csv_panel.csv_loaded, timeout=5000):
        win.csv_panel.load_path(str(FIXTURE))

    assert set(win.data_sources.keys()) == set(win.csv_panel._sources.keys())
    (source_id,) = win.data_sources.keys()

    win.csv_panel.close_source(source_id)

    assert set(win.data_sources.keys()) == set(win.csv_panel._sources.keys()) == set()
