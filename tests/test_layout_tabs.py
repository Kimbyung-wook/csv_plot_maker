"""Layout tabs: several independent layouts in the central area, each saved
and loaded on its own (Save/Load Tab) or all together (Save/Load Layout)."""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PySide6.QtWidgets import QDockWidget, QInputDialog, QMessageBox

from csv_plot_maker.data.column_store import ColumnStore
from csv_plot_maker.models.data_source import DataSource, SourceRef
from csv_plot_maker.models.project import ProjectState
from csv_plot_maker.models.serialization import (
    LayoutFile,
    default_tab_name,
    duplicate_tab_name,
    load_layout_file,
    save_project,
    save_workspace,
)
from csv_plot_maker.models.series import Series
from csv_plot_maker.ui.main_window import MainWindow


def _store() -> ColumnStore:
    store = ColumnStore(row_count=3)
    for name, values in (("Sequential", [1.0, 2.0, 3.0]), ("a", [1.0, 5.0, 2.0]), ("b", [7.0, 8.0, 9.0])):
        store.columns[name] = np.array(values)
        store.numeric[name] = True
    return store


def _open_csv(win: MainWindow, tmp_path: Path, source_id: str = "src", name: str = "data") -> DataSource:
    source = DataSource(
        id=source_id, path=str(tmp_path / f"{name}.csv"), label=name, color="#dbeafe", store=_store()
    )
    win._on_csv_loaded(source)
    return source


def _drop(win: MainWindow, source: DataSource, column: str) -> Series:
    subplot = win._active_subplot()
    win._on_column_dropped(subplot.row, subplot.col, source.id, column, move=False)
    return subplot.series[-1]


def _window(qtbot) -> MainWindow:
    win = MainWindow()
    qtbot.addWidget(win)
    return win


def _project(name: str = "", columns=("a",), source_id: str = "old") -> ProjectState:
    project = ProjectState(grid_rows=1, grid_cols=1, name=name)
    project.build_default_grid()
    project.data_sources = [SourceRef(id=source_id, path=f"{source_id}.csv", label=source_id, color="#111111")]
    for column in columns:
        project.subplots[0].add_series(Series(y_column=column, source_id=source_id, x_column="Sequential"))
    return project


# -- serialization ---------------------------------------------------------


def test_default_tab_name_takes_the_smallest_free_number():
    assert default_tab_name([]) == "Layout 1"
    assert default_tab_name(["Layout 1", "Layout 3"]) == "Layout 2"


def test_duplicate_tab_name_numbers_from_two():
    assert duplicate_tab_name("Temp", ["Temp"]) == "Temp (2)"
    assert duplicate_tab_name("Temp", ["Temp", "Temp (2)"]) == "Temp (3)"


def test_workspace_round_trips_tab_names_order_and_active_tab(tmp_path):
    path = tmp_path / "all.json"
    layout = LayoutFile(
        tabs=[_project("Pressure", ("a",)), _project("Speed", ("b",))], active_tab=1, legend_font_size=11
    )
    save_workspace(layout, str(path))

    loaded = load_layout_file(str(path))

    assert loaded.multi_tab
    assert [t.name for t in loaded.tabs] == ["Pressure", "Speed"]
    assert [t.subplots[0].series[0].y_column for t in loaded.tabs] == ["a", "b"]
    assert loaded.active_tab == 1
    assert loaded.legend_font_size == 11
    assert all(t.legend_font_size == 11 for t in loaded.tabs)
    assert "csv_path" not in json.loads(path.read_text(encoding="utf-8"))["tabs"][0]


def test_single_tab_file_loads_as_one_tab_named_after_the_file(tmp_path):
    path = tmp_path / "Engine run.json"
    save_project(_project("ignored"), str(path))

    loaded = load_layout_file(str(path))

    assert not loaded.multi_tab
    assert [t.name for t in loaded.tabs] == ["Engine run"]
    # The single-tab format doesn't store a name at all.
    assert "name" not in json.loads(path.read_text(encoding="utf-8"))


def test_clone_with_new_ids_keeps_contents_but_not_ids():
    project = _project("x", ("a", "b"))
    project.active_subplot_id = project.subplots[0].id

    clone = project.clone_with_new_ids()

    assert clone.subplots[0].id != project.subplots[0].id
    assert clone.active_subplot_id == clone.subplots[0].id
    assert [s.y_column for s in clone.subplots[0].series] == ["a", "b"]
    assert not {s.id for s in clone.subplots[0].series} & {s.id for s in project.subplots[0].series}


# -- tabs in the window ----------------------------------------------------


def test_window_starts_with_one_layout_tab(qtbot):
    win = _window(qtbot)

    assert win.layout_tabs.tab_names() == ["Layout 1"]
    assert not win.layout_tabs.tabsClosable()  # the last tab can't be closed


def test_each_tab_has_its_own_layout(qtbot, tmp_path):
    win = _window(qtbot)
    source = _open_csv(win, tmp_path)
    _drop(win, source, "a")
    first_project = win.project

    win._on_add_tab_requested()

    assert win.layout_tabs.tab_names() == ["Layout 1", "Layout 2"]
    assert win.project is not first_project
    assert not win.project.has_series()
    assert win.series_panel.series_list.count() == 0
    win.layout_tabs.setCurrentIndex(0)
    assert win.project is first_project
    assert win.series_panel.series_list.count() == 1


def test_rename_and_duplicate_tab(qtbot, tmp_path):
    win = _window(qtbot)
    source = _open_csv(win, tmp_path)
    series = _drop(win, source, "a")
    series.color = "#123456"

    win._on_rename_tab_requested(0, "Pressure")
    win._on_duplicate_tab_requested(0)

    assert win.layout_tabs.tab_names() == ["Pressure", "Pressure (2)"]
    assert win.layout_tabs.currentIndex() == 1
    copied = win.project.subplots[0].series[0]
    assert copied.color == "#123456"
    assert copied.id != series.id
    view = win.plot_grid.get_view(0, 0)
    assert copied.id in view._curves


def test_closing_a_tab_with_graphs_asks_first(qtbot, tmp_path):
    win = _window(qtbot)
    source = _open_csv(win, tmp_path)
    win._on_add_tab_requested()
    _drop(win, source, "a")

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        win._on_close_tab_requested(1)
    assert win.layout_tabs.count() == 2

    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        win._on_close_tab_requested(1)
    assert win.layout_tabs.tab_names() == ["Layout 1"]
    assert len(win._projects) == 1


def test_closing_an_empty_tab_does_not_ask_and_the_last_tab_stays(qtbot):
    win = _window(qtbot)
    win._on_add_tab_requested()

    with patch.object(QMessageBox, "question") as question:
        win._on_close_tab_requested(1)
        win._on_close_tab_requested(0)

    question.assert_not_called()
    assert win.layout_tabs.count() == 1


def test_closing_a_csv_removes_its_series_from_every_tab(qtbot, tmp_path):
    win = _window(qtbot)
    source = _open_csv(win, tmp_path)
    _drop(win, source, "a")
    win._on_add_tab_requested()
    _drop(win, source, "b")

    win._on_csv_closed(source.id)

    assert not any(p.has_series() for p in win._projects.values())


def test_close_all_files_resets_to_one_tab(qtbot, tmp_path):
    win = _window(qtbot)
    _open_csv(win, tmp_path)
    win._on_add_tab_requested()
    win._on_add_tab_requested()

    win._on_all_files_closed()

    assert win.layout_tabs.tab_names() == ["Layout 1"]
    assert len(win._projects) == 1
    assert win._layout_csv_path is None


def test_legend_font_size_applies_to_every_tab(qtbot):
    win = _window(qtbot)
    win._on_add_tab_requested()

    win._on_legend_font_size_changed(11)

    assert all(p.legend_font_size == 11 for p in win._projects.values())
    assert all(g._legend_font_pt == 11 for g in win._grids())
    win._on_add_tab_requested()
    assert win.project.legend_font_size == 11
    assert win.plot_grid._legend_font_pt == 11


# -- Save / Load Layout (every tab) ------------------------------------------


def _two_tab_window(qtbot, tmp_path) -> tuple[MainWindow, DataSource]:
    win = _window(qtbot)
    source = _open_csv(win, tmp_path)
    _drop(win, source, "a")
    win._on_rename_tab_requested(0, "Pressure")
    win._on_add_tab_requested()
    _drop(win, source, "b")
    win._on_rename_tab_requested(1, "Speed")
    return win, source


def test_save_layout_writes_every_tab_beside_the_csv(qtbot, tmp_path):
    win, _source = _two_tab_window(qtbot, tmp_path)

    win._on_save_config()

    loaded = load_layout_file(str(tmp_path / "data.json"))
    assert [t.name for t in loaded.tabs] == ["Pressure", "Speed"]
    assert loaded.active_tab == 1
    assert all(t.data_sources[0].label == "data" for t in loaded.tabs)


def test_opening_the_csv_again_restores_every_saved_tab(qtbot, tmp_path):
    win, _source = _two_tab_window(qtbot, tmp_path)
    win._on_save_config()

    win2 = _window(qtbot)
    _open_csv(win2, tmp_path, source_id="new-id")

    assert win2.layout_tabs.tab_names() == ["Pressure", "Speed"]
    assert win2.layout_tabs.currentIndex() == 1
    for grid in win2._grids():
        series = win2._projects[grid].subplots[0].series[0]
        assert series.source_id == "new-id"
        assert series.id in grid.get_view(0, 0)._curves
    assert win2.series_panel.series_list.count() == 1


def test_load_layout_replace_and_append(qtbot, tmp_path):
    win, _source = _two_tab_window(qtbot, tmp_path)
    path = tmp_path / "saved.json"
    save_workspace(win._collect_layout(), str(path))
    win._on_add_tab_requested()

    win._load_layout_from_path(str(path), mode="append")
    assert win.layout_tabs.tab_names() == ["Pressure", "Speed", "Layout 1", "Pressure (2)", "Speed (2)"]
    assert win.layout_tabs.currentIndex() == 4  # the file's active tab, among the added ones

    win._load_layout_from_path(str(path), mode="replace")
    assert win.layout_tabs.tab_names() == ["Pressure", "Speed"]
    assert len(win._projects) == 2


def test_load_layout_asks_and_cancel_changes_nothing(qtbot, tmp_path):
    win, _source = _two_tab_window(qtbot, tmp_path)
    path = tmp_path / "saved.json"
    save_workspace(win._collect_layout(), str(path))
    win._on_add_tab_requested()

    with patch.object(win, "_ask_replace_or_append", return_value="") as ask:
        win._load_layout_from_path(str(path))

    ask.assert_called_once()
    assert win.layout_tabs.tab_names() == ["Pressure", "Speed", "Layout 1"]


def test_load_layout_replace_applies_the_files_legend_font_size(qtbot, tmp_path):
    win, _source = _two_tab_window(qtbot, tmp_path)
    layout = win._collect_layout()
    layout.legend_font_size = 5
    path = tmp_path / "saved.json"
    save_workspace(layout, str(path))
    win._on_legend_font_size_changed(11)

    win._load_layout_from_path(str(path), mode="replace")

    assert win._legend_font_size == 5
    assert all(g._legend_font_pt == 5 for g in win._grids())
    assert win._legend_font_actions[5].isChecked()


# -- Save / Load Tab (one tab) -------------------------------------------------


def test_save_tab_writes_only_the_current_tab(qtbot, tmp_path):
    win, _source = _two_tab_window(qtbot, tmp_path)
    path = tmp_path / "one.json"

    win._save_tab_to_path(str(path))

    loaded = load_layout_file(str(path))
    assert not loaded.multi_tab
    assert [s.y_column for s in loaded.tabs[0].subplots[0].series] == ["b"]


def test_save_tab_default_file_name_is_the_tab_name_beside_the_csv(qtbot, tmp_path):
    win, _source = _two_tab_window(qtbot, tmp_path)
    win._on_rename_tab_requested(1, 'Speed: 1/2?')

    assert Path(win._default_tab_file_path()) == tmp_path / "Speed_ 1_2_.json"


def test_load_tab_into_the_current_tab_names_it_after_the_file(qtbot, tmp_path):
    win, _source = _two_tab_window(qtbot, tmp_path)
    path = tmp_path / "Engine.json"
    save_project(_project(columns=("a", "b")), str(path))

    win._load_tab_from_path(str(path), new_tab=False)

    assert win.layout_tabs.tab_names() == ["Pressure", "Engine"]
    assert [s.y_column for s in win.project.subplots[0].series] == ["a", "b"]
    assert all(s.source_id == "src" for s in win.project.subplots[0].series)
    assert win.series_panel.series_list.count() == 2


def test_load_tab_as_new_from_a_multi_tab_file_picks_one_tab(qtbot, tmp_path):
    win, _source = _two_tab_window(qtbot, tmp_path)
    path = tmp_path / "saved.json"
    save_workspace(win._collect_layout(), str(path))
    win.layout_tabs.setCurrentIndex(0)

    with patch.object(QInputDialog, "getItem", return_value=("Speed", True)) as get_item:
        win._load_tab_from_path(str(path), new_tab=True)

    get_item.assert_called_once()
    assert win.layout_tabs.tab_names() == ["Pressure", "Speed (2)", "Speed"]
    assert win.layout_tabs.currentIndex() == 1
    assert [s.y_column for s in win.project.subplots[0].series] == ["b"]


def test_layout_menu_items_need_an_open_csv(qtbot):
    win = _window(qtbot)

    with patch.object(QMessageBox, "warning") as warning, patch(
        "csv_plot_maker.ui.main_window.QFileDialog.getOpenFileName"
    ) as dialog:
        win._on_load_tab_as()
        win._on_load_tab_as_new()
        win._on_load_config()

    assert warning.call_count == 3
    dialog.assert_not_called()


def test_add_button_sits_right_after_the_last_tab(qtbot):
    win = _window(qtbot)
    win.resize(1000, 500)
    for dock in win.findChildren(QDockWidget):  # give the tab bar room
        dock.hide()
    win.show()
    qtbot.waitExposed(win)
    bar = win.layout_tabs.tabBar()

    def assert_after_last_tab():
        qtbot.wait(10)
        assert win.layout_tabs.add_button.geometry().left() == bar.tabRect(bar.count() - 1).right() + 1

    assert_after_last_tab()
    win._on_add_tab_requested()
    win._on_rename_tab_requested(1, "A much longer tab name")
    assert_after_last_tab()
    win._on_close_tab_requested(1)
    assert_after_last_tab()

    win.layout_tabs.add_button.click()
    assert win.layout_tabs.count() == 2


def test_tab_list_and_pinned_add_button_appear_only_when_tabs_overflow(qtbot):
    win = _window(qtbot)
    win.resize(1000, 500)
    win.show()
    qtbot.waitExposed(win)
    tabs = win.layout_tabs
    qtbot.wait(10)
    assert not tabs.is_overflowing()
    assert not tabs.list_button.isVisible()
    assert not tabs.corner_add_button.isVisible()

    while tabs.tabBar().tabs_width() <= tabs.width():
        win._on_add_tab_requested()
    qtbot.wait(10)
    assert tabs.is_overflowing()
    assert tabs.list_button.isVisible()
    assert tabs.corner_add_button.isVisible()
    assert not tabs.add_button.isVisible()  # the in-bar "+" gives way

    menu = tabs.tab_list_menu()
    actions = menu.actions()
    assert [a.text() for a in actions] == tabs.tab_names()
    assert [a.isChecked() for a in actions].index(True) == tabs.currentIndex()
    actions[0].trigger()
    assert tabs.currentIndex() == 0

    count = tabs.count()
    tabs.corner_add_button.click()
    assert tabs.count() == count + 1

    while tabs.count() > 1:
        win._on_close_tab_requested(tabs.count() - 1)
    qtbot.wait(10)
    assert not tabs.is_overflowing()
    assert not tabs.list_button.isVisible()
    assert not tabs.corner_add_button.isVisible()
    assert tabs.add_button.isVisible()
