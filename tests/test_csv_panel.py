from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from csv_plot_maker.models.data_source import DataSource
from csv_plot_maker.ui.csv_panel import CsvPanel, _HEADER_SOURCE_ID_ROLE

FIXTURE = Path(__file__).parent / "fixtures" / "small.csv"


def test_confirm_memory_headroom_passes_when_plenty_of_ram(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)

    with patch("csv_plot_maker.ui.csv_panel.os.path.getsize", return_value=1_000_000):
        with patch("csv_plot_maker.ui.csv_panel.psutil.virtual_memory") as mock_vm:
            mock_vm.return_value.available = 16_000_000_000
            assert panel._confirm_memory_headroom("dummy.csv") is True


def test_confirm_memory_headroom_warns_and_respects_no(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)

    # A 10 GB file against 4 GB available RAM should trip the warning.
    with patch("csv_plot_maker.ui.csv_panel.os.path.getsize", return_value=10_000_000_000):
        with patch("csv_plot_maker.ui.csv_panel.psutil.virtual_memory") as mock_vm:
            mock_vm.return_value.available = 4_000_000_000
            with patch(
                "csv_plot_maker.ui.csv_panel.QMessageBox.warning",
                return_value=QMessageBox.StandardButton.No,
            ) as mock_warning:
                assert panel._confirm_memory_headroom("dummy.csv") is False
                assert mock_warning.called


def test_confirm_memory_headroom_warns_and_respects_yes(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)

    with patch("csv_plot_maker.ui.csv_panel.os.path.getsize", return_value=10_000_000_000):
        with patch("csv_plot_maker.ui.csv_panel.psutil.virtual_memory") as mock_vm:
            mock_vm.return_value.available = 4_000_000_000
            with patch(
                "csv_plot_maker.ui.csv_panel.QMessageBox.warning",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                assert panel._confirm_memory_headroom("dummy.csv") is True


def test_load_path_applies_header_trim_keywords_end_to_end(qtbot):
    # small.csv has columns t, a, b, label -- stripping "lab" should rename
    # "label" to "el" all the way through the background load, not just in
    # the immediately-populated column list.
    panel = CsvPanel()
    qtbot.addWidget(panel)
    panel._header_trim_keywords = ["lab"]

    with qtbot.waitSignal(panel.csv_loaded, timeout=5000) as blocker:
        panel.load_path(str(FIXTURE))

    source = blocker.args[0]
    store = source.store
    assert "el" in store.dtypes
    assert "label" not in store.dtypes
    column_list_names = [panel.column_list.item(i).text() for i in range(panel.column_list.count())]
    assert "el" in column_list_names


def test_header_trim_dialog_reloads_the_open_csv_when_keywords_changed(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    panel._sources["src1"] = DataSource(id="src1", path="dummy.csv", label="dummy", color="#dbeafe")
    panel._header_trim_keywords = ["foo"]

    with patch("csv_plot_maker.ui.csv_panel.HeaderTrimDialog") as mock_dialog_cls:
        mock_dialog_cls.return_value.exec.return_value = None
        mock_dialog_cls.return_value.current_keywords.return_value = ["foo", "bar"]
        with patch.object(panel, "load_path") as mock_load_path:
            panel._on_header_trim_clicked()

    assert panel._header_trim_keywords == ["foo", "bar"]
    mock_load_path.assert_called_once_with("dummy.csv", source_id="src1")


def test_header_trim_dialog_does_not_reload_when_keywords_unchanged(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    panel._current_path = "dummy.csv"
    panel._header_trim_keywords = ["foo"]

    with patch("csv_plot_maker.ui.csv_panel.HeaderTrimDialog") as mock_dialog_cls:
        mock_dialog_cls.return_value.exec.return_value = None
        mock_dialog_cls.return_value.current_keywords.return_value = ["foo"]
        with patch.object(panel, "load_path") as mock_load_path:
            panel._on_header_trim_clicked()

    mock_load_path.assert_not_called()


def test_header_trim_dialog_does_not_reload_when_no_csv_is_open(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    assert panel._sources == {}
    panel._header_trim_keywords = []

    with patch("csv_plot_maker.ui.csv_panel.HeaderTrimDialog") as mock_dialog_cls:
        mock_dialog_cls.return_value.exec.return_value = None
        mock_dialog_cls.return_value.current_keywords.return_value = ["foo"]
        with patch.object(panel, "load_path") as mock_load_path:
            panel._on_header_trim_clicked()

    assert panel._header_trim_keywords == ["foo"]
    mock_load_path.assert_not_called()


def test_ctrl_a_does_not_select_all_columns(qtbot):
    # Select-all lives on the subplot's own series list instead (right-hand
    # panel) -- the Data tab's column list must not also respond to it.
    panel = CsvPanel()
    qtbot.addWidget(panel)
    panel.column_list.addItems(["t", "a", "b", "label"])
    panel.column_list.setFocus()

    QTest.keyClick(panel.column_list, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)

    assert len(panel.column_list.selectedItems()) == 0


def test_single_open_file_hides_its_header_and_column_color(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    source = DataSource(id="a", path="a.csv", label="a", color="#dbeafe")
    panel._sources["a"] = source
    panel.column_list.set_source_group(source, ["alt", "spd"])

    panel._sync_group_chrome()

    header = panel.column_list.item(0)
    assert header.isHidden() is True
    for row in (1, 2):
        assert panel.column_list.item(row).background().style() == Qt.BrushStyle.NoBrush


def test_second_open_file_reveals_both_headers_and_colors(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    source_a = DataSource(id="a", path="a.csv", label="a", color="#dbeafe")
    source_b = DataSource(id="b", path="b.csv", label="b", color="#dcfce7")
    panel._sources["a"] = source_a
    panel._sources["b"] = source_b
    panel.column_list.set_source_group(source_a, ["alt"])
    panel.column_list.set_source_group(source_b, ["spd"])

    panel._sync_group_chrome()

    headers = [
        panel.column_list.item(row)
        for row in range(panel.column_list.count())
        if panel.column_list.item(row).data(_HEADER_SOURCE_ID_ROLE) is not None
    ]
    assert len(headers) == 2
    assert all(h.isHidden() is False for h in headers)


def test_closing_back_down_to_one_file_hides_chrome_again(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    source_a = DataSource(id="a", path="a.csv", label="a", color="#dbeafe")
    source_b = DataSource(id="b", path="b.csv", label="b", color="#dcfce7")
    panel._sources["a"] = source_a
    panel._sources["b"] = source_b
    panel.column_list.set_source_group(source_a, ["alt"])
    panel.column_list.set_source_group(source_b, ["spd"])
    panel._sync_group_chrome()

    panel.close_source("b")

    remaining_header = next(
        panel.column_list.item(row)
        for row in range(panel.column_list.count())
        if panel.column_list.item(row).data(_HEADER_SOURCE_ID_ROLE) is not None
    )
    assert remaining_header.isHidden() is True


def test_rename_source_updates_label_and_header_text(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    source = DataSource(id="a", path=r"C:\very\long\path\flight_recorder_export_2026.csv", label="flight_recorder_export_2026", color="#dbeafe")
    panel._sources["a"] = source
    panel.column_list.set_source_group(source, ["alt", "spd"])

    received = []
    panel.source_renamed.connect(received.append)
    with patch("csv_plot_maker.ui.csv_panel.QInputDialog.getText", return_value=("flight1", True)):
        panel._rename_source("a")

    assert source.label == "flight1"
    assert panel.column_list.item(0).text() == "\u25be flight1"
    assert received == ["a"]
    assert "flight1" in panel.path_label.text()


def test_clicking_a_header_collapses_and_expands_its_columns(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    source = DataSource(id="a", path="a.csv", label="a", color="#dbeafe")
    panel._sources["a"] = source
    panel.column_list.set_source_group(source, ["alt", "spd"])
    header = panel.column_list.item(0)

    with qtbot.waitSignal(panel.column_list.itemClicked, timeout=1000):
        QTest.mouseClick(
            panel.column_list.viewport(),
            Qt.MouseButton.LeftButton,
            pos=panel.column_list.visualItemRect(header).center(),
        )

    assert header.text() == "\u25b8 a"
    assert panel.column_list.item(1).isHidden() is True
    assert panel.column_list.item(2).isHidden() is True

    with qtbot.waitSignal(panel.column_list.itemClicked, timeout=1000):
        QTest.mouseClick(
            panel.column_list.viewport(),
            Qt.MouseButton.LeftButton,
            pos=panel.column_list.visualItemRect(header).center(),
        )

    assert header.text() == "\u25be a"
    assert panel.column_list.item(1).isHidden() is False
    assert panel.column_list.item(2).isHidden() is False


def test_collapsing_a_group_clears_selection_on_its_hidden_columns(qtbot):
    # Qt does not auto-deselect a hidden item, so a still-selected column in
    # a collapsed (invisible) group could otherwise still be dragged out via
    # startDrag()'s selectedItems().
    panel = CsvPanel()
    qtbot.addWidget(panel)
    source = DataSource(id="a", path="a.csv", label="a", color="#dbeafe")
    panel._sources["a"] = source
    panel.column_list.set_source_group(source, ["alt", "spd"])
    panel.column_list.item(1).setSelected(True)

    panel.column_list.toggle_group_collapsed("a")

    assert panel.column_list.selectedItems() == []


def test_collapsed_group_columns_excluded_from_ctrl_f_search(qtbot):
    from csv_plot_maker.ui.csv_panel import ColumnSearchPopup

    panel = CsvPanel()
    qtbot.addWidget(panel)
    source = DataSource(id="a", path="a.csv", label="a", color="#dbeafe")
    panel._sources["a"] = source
    panel.column_list.set_source_group(source, ["alt", "spd"])
    panel.column_list.toggle_group_collapsed("a")

    popup = ColumnSearchPopup(panel.column_list)
    qtbot.addWidget(popup)
    popup._on_text_changed("alt")

    assert popup._matches == []


def test_reloading_an_open_source_preserves_collapsed_state(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    source = DataSource(id="a", path="a.csv", label="a", color="#dbeafe")
    panel._sources["a"] = source
    panel.column_list.set_source_group(source, ["alt", "spd"])
    panel.column_list.toggle_group_collapsed("a")

    # Simulate a Header Trimming reload: same source_id, rebuilt rows.
    panel.column_list.set_source_group(source, ["alt", "spd", "hdg"])

    assert panel.column_list.is_group_collapsed("a") is True
    for row in range(1, panel.column_list.count()):
        assert panel.column_list.item(row).isHidden() is True


def test_second_file_opening_does_not_reveal_an_already_collapsed_group(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    source_a = DataSource(id="a", path="a.csv", label="a", color="#dbeafe")
    panel._sources["a"] = source_a
    panel.column_list.set_source_group(source_a, ["alt"])
    panel.column_list.toggle_group_collapsed("a")

    source_b = DataSource(id="b", path="b.csv", label="b", color="#dcfce7")
    panel._sources["b"] = source_b
    panel.column_list.set_source_group(source_b, ["spd"])
    panel._sync_group_chrome()

    alt_row = next(
        row
        for row in range(panel.column_list.count())
        if panel.column_list.item(row).text() == "alt"
    )
    assert panel.column_list.item(alt_row).isHidden() is True


def test_rename_source_ignores_cancel(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    source = DataSource(id="a", path="a.csv", label="original", color="#dbeafe")
    panel._sources["a"] = source
    panel.column_list.set_source_group(source, ["alt"])

    received = []
    panel.source_renamed.connect(received.append)
    with patch("csv_plot_maker.ui.csv_panel.QInputDialog.getText", return_value=("something else", False)):
        panel._rename_source("a")

    assert source.label == "original"
    assert received == []


def test_rename_source_rejects_duplicate_label(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    panel._sources["a"] = DataSource(id="a", path="a.csv", label="alpha", color="#dbeafe")
    panel._sources["b"] = DataSource(id="b", path="b.csv", label="beta", color="#dcfce7")

    received = []
    panel.source_renamed.connect(received.append)
    with patch("csv_plot_maker.ui.csv_panel.QInputDialog.getText", return_value=("alpha", True)):
        with patch("csv_plot_maker.ui.csv_panel.QMessageBox.warning") as mock_warning:
            panel._rename_source("b")

    assert panel._sources["b"].label == "beta"
    assert mock_warning.called
    assert received == []


def test_close_all_files_clears_every_source_when_confirmed(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    panel._sources["a"] = DataSource(id="a", path="a.csv", label="a", color="#dbeafe")
    panel._sources["b"] = DataSource(id="b", path="b.csv", label="b", color="#dcfce7")
    panel.column_list.set_source_group(panel._sources["a"], ["x"])
    panel.column_list.set_source_group(panel._sources["b"], ["y"])

    received = []
    panel.all_files_closed.connect(lambda: received.append(True))
    with patch(
        "csv_plot_maker.ui.csv_panel.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        panel._on_close_all_clicked()

    assert panel._sources == {}
    assert panel.column_list.count() == 0
    assert panel.path_label.text() == "No file loaded"
    assert received == [True]


def test_close_all_files_does_nothing_when_canceled(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    panel._sources["a"] = DataSource(id="a", path="a.csv", label="a", color="#dbeafe")

    received = []
    panel.all_files_closed.connect(lambda: received.append(True))
    with patch(
        "csv_plot_maker.ui.csv_panel.QMessageBox.question",
        return_value=QMessageBox.StandardButton.No,
    ):
        panel._on_close_all_clicked()

    assert "a" in panel._sources
    assert received == []


def test_close_all_files_button_is_a_noop_with_nothing_open(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)

    with patch("csv_plot_maker.ui.csv_panel.QMessageBox.question") as mock_question:
        panel._on_close_all_clicked()

    mock_question.assert_not_called()


def test_confirm_memory_headroom_fails_open_on_missing_file(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)

    # A nonexistent path makes os.path.getsize raise OSError -- the check
    # must not block the load itself (load_path's own peek_schema() is the
    # thing that will actually report a missing/unreadable file).
    assert panel._confirm_memory_headroom(r"C:\does\not\exist.csv") is True
