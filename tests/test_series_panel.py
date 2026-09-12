from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView

from csv_plot_maker.ui.series_panel import SeriesPanel


def _add_series_items(panel: SeriesPanel, ids: list[str]) -> None:
    panel.refresh_series_list([(series_id, "src", series_id, series_id, "") for series_id in ids])


def test_series_list_uses_extended_selection_mode(qtbot):
    panel = SeriesPanel()
    qtbot.addWidget(panel)

    assert panel.series_list.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection


def test_series_list_is_drag_enabled(qtbot):
    panel = SeriesPanel()
    qtbot.addWidget(panel)

    assert panel.series_list.dragEnabled() is True


def test_delete_key_emits_a_request_per_selected_series(qtbot):
    panel = SeriesPanel()
    qtbot.addWidget(panel)
    _add_series_items(panel, ["a", "b", "c"])
    panel.series_list.item(0).setSelected(True)
    panel.series_list.item(2).setSelected(True)

    received = []
    panel.series_delete_requested.connect(received.append)

    panel.series_list.delete_requested.emit()

    assert sorted(received) == ["a", "c"]


def test_ctrl_a_selects_every_series_row(qtbot):
    panel = SeriesPanel()
    qtbot.addWidget(panel)
    _add_series_items(panel, ["a", "b", "c"])
    panel.series_list.setFocus()

    QTest.keyClick(panel.series_list, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)

    assert len(panel.series_list.selectedItems()) == 3


def test_drag_exports_the_y_column_of_every_selected_series(qtbot):
    panel = SeriesPanel()
    qtbot.addWidget(panel)
    panel.refresh_series_list(
        [
            ("id1", "src1", "temp", "temp  [primary]", ""),
            ("id2", "src2", "pressure", "pressure  [secondary]", ""),
        ]
    )
    panel.series_list.item(0).setSelected(True)
    panel.series_list.item(1).setSelected(True)

    captured = {}
    with patch("csv_plot_maker.ui.column_drag.QDrag") as mock_drag_cls:
        mock_drag_cls.return_value.setMimeData.side_effect = lambda mime: captured.update(text=mime.text())
        panel.series_list.startDrag(Qt.DropAction.CopyAction)

    assert captured["text"] == "src1\ttemp\nsrc2\tpressure"


def test_click_drag_does_not_extend_the_selection(qtbot):
    # Regression guard: once the list is a drag source, a press-and-move on a
    # selected row must start a drag instead of falling back to Qt's default
    # "extend selection while dragging" behavior for ExtendedSelection.
    panel = SeriesPanel()
    qtbot.addWidget(panel)
    panel.refresh_series_list(
        [("id1", "src", "a", "a", ""), ("id2", "src", "b", "b", ""), ("id3", "src", "c", "c", "")]
    )
    panel.show()
    qtbot.waitExposed(panel)
    list_widget = panel.series_list
    rect_first = list_widget.visualItemRect(list_widget.item(0))
    rect_last = list_widget.visualItemRect(list_widget.item(2))

    with patch("csv_plot_maker.ui.column_drag.QDrag"):
        QTest.mousePress(list_widget.viewport(), Qt.MouseButton.LeftButton, pos=rect_first.center())
        QTest.mouseMove(list_widget.viewport(), rect_last.center())
        selected_mid_drag = [item.text() for item in list_widget.selectedItems()]
        QTest.mouseRelease(list_widget.viewport(), Qt.MouseButton.LeftButton, pos=rect_last.center())

    assert selected_mid_drag == ["a"]
