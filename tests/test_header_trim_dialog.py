from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from csv_plot_maker.ui.header_trim_dialog import HeaderTrimDialog


def test_dialog_shows_the_keywords_it_was_given(qtbot):
    dialog = HeaderTrimDialog(["foo", "bar"])
    qtbot.addWidget(dialog)

    assert dialog.current_keywords() == ["foo", "bar"]


def test_add_keyword_updates_current_keywords_without_touching_disk(qtbot):
    dialog = HeaderTrimDialog(["foo"])
    qtbot.addWidget(dialog)

    with patch("csv_plot_maker.ui.header_trim_dialog.save_keywords_to_file") as mock_save:
        dialog._input.setText("bar")
        dialog._on_add()

    mock_save.assert_not_called()
    assert dialog.current_keywords() == ["foo", "bar"]
    assert dialog._input.text() == ""


def test_add_duplicate_keyword_is_ignored(qtbot):
    dialog = HeaderTrimDialog(["foo"])
    qtbot.addWidget(dialog)

    dialog._input.setText("foo")
    dialog._on_add()

    assert dialog.current_keywords() == ["foo"]


def test_remove_selected_keyword_updates_current_keywords(qtbot):
    dialog = HeaderTrimDialog(["foo", "bar"])
    qtbot.addWidget(dialog)

    dialog._list.setCurrentRow(0)
    dialog._on_remove_selected()

    assert dialog.current_keywords() == ["bar"]


def test_remove_all_clears_every_keyword_when_confirmed(qtbot):
    dialog = HeaderTrimDialog(["foo", "bar", "baz"])
    qtbot.addWidget(dialog)

    with patch(
        "csv_plot_maker.ui.header_trim_dialog.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        dialog._on_remove_all()

    assert dialog.current_keywords() == []


def test_remove_all_keeps_keywords_when_declined(qtbot):
    dialog = HeaderTrimDialog(["foo", "bar"])
    qtbot.addWidget(dialog)

    with patch(
        "csv_plot_maker.ui.header_trim_dialog.QMessageBox.question",
        return_value=QMessageBox.StandardButton.No,
    ):
        dialog._on_remove_all()

    assert dialog.current_keywords() == ["foo", "bar"]


def test_remove_all_on_empty_list_does_not_prompt(qtbot):
    dialog = HeaderTrimDialog([])
    qtbot.addWidget(dialog)

    with patch("csv_plot_maker.ui.header_trim_dialog.QMessageBox.question") as mock_question:
        dialog._on_remove_all()

    mock_question.assert_not_called()


def test_load_from_file_replaces_current_keywords(qtbot):
    dialog = HeaderTrimDialog(["foo"])
    qtbot.addWidget(dialog)

    with patch("csv_plot_maker.ui.header_trim_dialog.QFileDialog.getOpenFileName", return_value=("picked.json", "")):
        with patch("csv_plot_maker.ui.header_trim_dialog.load_keywords_from_file", return_value=["loaded_a", "loaded_b"]):
            dialog._on_load_from_file()

    assert dialog.current_keywords() == ["loaded_a", "loaded_b"]


def test_load_from_file_cancelled_leaves_keywords_unchanged(qtbot):
    dialog = HeaderTrimDialog(["foo"])
    qtbot.addWidget(dialog)

    with patch("csv_plot_maker.ui.header_trim_dialog.QFileDialog.getOpenFileName", return_value=("", "")):
        dialog._on_load_from_file()

    assert dialog.current_keywords() == ["foo"]


def test_load_from_file_shows_warning_on_failure_and_keeps_old_list(qtbot):
    dialog = HeaderTrimDialog(["foo"])
    qtbot.addWidget(dialog)

    with patch("csv_plot_maker.ui.header_trim_dialog.QFileDialog.getOpenFileName", return_value=("bad.json", "")):
        with patch("csv_plot_maker.ui.header_trim_dialog.load_keywords_from_file", side_effect=ValueError("bad json")):
            with patch("csv_plot_maker.ui.header_trim_dialog.QMessageBox.warning") as mock_warning:
                dialog._on_load_from_file()

    mock_warning.assert_called_once()
    assert dialog.current_keywords() == ["foo"]


def test_save_to_file_writes_current_keywords(qtbot):
    dialog = HeaderTrimDialog(["foo", "bar"])
    qtbot.addWidget(dialog)

    with patch("csv_plot_maker.ui.header_trim_dialog.QFileDialog.getSaveFileName", return_value=("picked.json", "")):
        with patch("csv_plot_maker.ui.header_trim_dialog.save_keywords_to_file") as mock_save:
            dialog._on_save_to_file()

    mock_save.assert_called_once_with("picked.json", ["foo", "bar"])


def test_save_to_file_cancelled_does_not_write(qtbot):
    dialog = HeaderTrimDialog(["foo"])
    qtbot.addWidget(dialog)

    with patch("csv_plot_maker.ui.header_trim_dialog.QFileDialog.getSaveFileName", return_value=("", "")):
        with patch("csv_plot_maker.ui.header_trim_dialog.save_keywords_to_file") as mock_save:
            dialog._on_save_to_file()

    mock_save.assert_not_called()
