from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from csv_plot_maker.ui.header_trim_settings import (
    app_dir,
    load_keywords_from_file,
    save_keywords_to_file,
)


class HeaderTrimDialog(QDialog):
    """Edit the list of substrings stripped from every CSV column header.

    Each keyword is removed (as plain text, wherever it appears) from every
    column name the next time a CSV is opened -- e.g. a message-namespace
    prefix like "AVS_TC_AILDA::" or a decoded-field suffix like "_Value".

    Add/Remove only edit this dialog's own in-memory list -- nothing is
    written to disk on its own. Persisting or reusing a list across app
    restarts or machines is an explicit action via "Load from File..." /
    "Save to File...", not something the app does automatically.
    """

    def __init__(self, keywords: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Header Trimming")
        self.setModal(True)
        self.resize(360, 340)

        self._list = QListWidget()
        self._list.addItems(keywords)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Keyword to strip from headers...")
        add_button = QPushButton("Add")
        remove_button = QPushButton("Remove Selected")
        load_button = QPushButton("Load from File...")
        save_button = QPushButton("Save to File...")
        close_button = QPushButton("Close")

        input_row = QHBoxLayout()
        input_row.addWidget(self._input, 1)
        input_row.addWidget(add_button)

        file_row = QHBoxLayout()
        file_row.addWidget(load_button)
        file_row.addWidget(save_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Keywords removed from every column header on load:"))
        layout.addWidget(self._list, 1)
        layout.addLayout(input_row)
        layout.addWidget(remove_button)
        layout.addLayout(file_row)
        layout.addWidget(close_button)

        self._input.returnPressed.connect(self._on_add)
        add_button.clicked.connect(self._on_add)
        remove_button.clicked.connect(self._on_remove_selected)
        load_button.clicked.connect(self._on_load_from_file)
        save_button.clicked.connect(self._on_save_to_file)
        close_button.clicked.connect(self.accept)

    def current_keywords(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def _on_add(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        if text in self.current_keywords():
            self._input.clear()
            return
        self._list.addItem(text)
        self._input.clear()

    def _on_remove_selected(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))

    def _on_load_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Keyword List", str(app_dir()), "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            keywords = load_keywords_from_file(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Load failed", f"Could not load keyword list:\n{exc}")
            return
        self._list.clear()
        self._list.addItems(keywords)

    def _on_save_to_file(self) -> None:
        default_path = str(app_dir() / "header_trim_keywords.json")
        path, _ = QFileDialog.getSaveFileName(self, "Save Keyword List", default_path, "JSON Files (*.json)")
        if not path:
            return
        try:
            save_keywords_to_file(path, self.current_keywords())
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", f"Could not save keyword list:\n{exc}")
