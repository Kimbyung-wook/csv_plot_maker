from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from csv_plot_maker.ui.csv_panel import CsvPanel


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


def test_confirm_memory_headroom_fails_open_on_missing_file(qtbot):
    panel = CsvPanel()
    qtbot.addWidget(panel)

    # A nonexistent path makes os.path.getsize raise OSError -- the check
    # must not block the load itself (load_path's own peek_schema() is the
    # thing that will actually report a missing/unreadable file).
    assert panel._confirm_memory_headroom(r"C:\does\not\exist.csv") is True
