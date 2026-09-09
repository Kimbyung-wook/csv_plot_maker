from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from csv_plot_maker.ui.csv_panel import CsvPanel

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

    store = blocker.args[0]
    assert "el" in store.dtypes
    assert "label" not in store.dtypes
    column_list_names = [panel.column_list.item(i).text() for i in range(panel.column_list.count())]
    assert "el" in column_list_names


def test_header_trim_dialog_reloads_the_open_csv_when_keywords_changed(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)
    panel._current_path = "dummy.csv"
    panel._header_trim_keywords = ["foo"]

    with patch("csv_plot_maker.ui.csv_panel.HeaderTrimDialog") as mock_dialog_cls:
        mock_dialog_cls.return_value.exec.return_value = None
        mock_dialog_cls.return_value.current_keywords.return_value = ["foo", "bar"]
        with patch.object(panel, "load_path") as mock_load_path:
            panel._on_header_trim_clicked()

    assert panel._header_trim_keywords == ["foo", "bar"]
    mock_load_path.assert_called_once_with("dummy.csv")


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
    assert panel._current_path is None
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


def test_confirm_memory_headroom_fails_open_on_missing_file(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)

    # A nonexistent path makes os.path.getsize raise OSError -- the check
    # must not block the load itself (load_path's own peek_schema() is the
    # thing that will actually report a missing/unreadable file).
    assert panel._confirm_memory_headroom(r"C:\does\not\exist.csv") is True
