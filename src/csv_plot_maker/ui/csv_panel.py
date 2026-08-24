from __future__ import annotations

import os

import psutil
from PySide6.QtCore import QMimeData, QThreadPool, Qt, Signal
from PySide6.QtGui import QDrag, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from csv_plot_maker.data.column_store import ColumnStore
from csv_plot_maker.data.loader import load_csv, peek_schema
from csv_plot_maker.utils.workers import CallableWorker

# How many times a CSV's on-disk size a full load might need in RAM at peak,
# even after loader.py's own memory-reduction steps (skipping non-numeric
# columns, releasing polars' own copy of each column as it converts) --
# polars' CSV parser itself still uses working buffers beyond the final
# DataFrame, and numeric text doesn't map 1:1 to its binary size. Deliberately
# conservative: a false-positive warning costs the user two clicks, a false
# negative can hang their whole machine.
_MEMORY_WARNING_MULTIPLIER = 2.0


class DraggableColumnList(QListWidget):
    """Column list that exports every selected column name as plain-text MIME data.

    Shift-click selects a contiguous range, Ctrl-click toggles individual
    columns in/out of the selection (both native to ExtendedSelection mode),
    and dragging the selection onto a subplot in the plot grid adds all of
    them as Y series there in one drop, instead of hunting for each one in a
    combo box one at a time.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def startDrag(self, supportedActions) -> None:
        items = self.selectedItems()
        if not items:
            return
        mime = QMimeData()
        mime.setText("\n".join(item.text() for item in items))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class ColumnSearchPopup(QDialog):
    """Non-modal Ctrl+F popup: type to jump the column list to a match."""

    def __init__(self, list_widget: QListWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Find Column")
        self.setModal(False)
        self._list = list_widget
        self._matches: list[int] = []
        self._match_pos = -1

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Type to search columns... (Enter for next match)")
        self._status_label = QLabel("")

        layout = QVBoxLayout(self)
        layout.addWidget(self._search_edit)
        layout.addWidget(self._status_label)

        self._search_edit.textChanged.connect(self._on_text_changed)
        self._search_edit.returnPressed.connect(self._find_next)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._search_edit.setFocus()
        self._search_edit.selectAll()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def _on_text_changed(self, text: str) -> None:
        self._matches = [
            row
            for row in range(self._list.count())
            if text and text.lower() in self._list.item(row).text().lower()
        ]
        self._match_pos = 0 if self._matches else -1
        if self._matches:
            self._select_current_match()
        else:
            self._status_label.setText("No matches" if text else "")

    def _find_next(self) -> None:
        if not self._matches:
            return
        self._match_pos = (self._match_pos + 1) % len(self._matches)
        self._select_current_match()

    def _select_current_match(self) -> None:
        item = self._list.item(self._matches[self._match_pos])
        self._list.setCurrentItem(item)
        self._list.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
        self._status_label.setText(f"Match {self._match_pos + 1} of {len(self._matches)}")


class CsvPanel(QWidget):
    """Data tab: open a CSV, show its columns immediately, load full data in the background."""

    csv_loaded = Signal(object)  # emits ColumnStore once the background load finishes

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._search_popup: ColumnSearchPopup | None = None
        self._progress: QProgressDialog | None = None
        # Bumped on every load_path() call so a stale worker signal from a
        # superseded load (user opened another CSV before the first one
        # finished) can be told apart from the one currently in flight.
        self._load_generation = 0
        # generation -> (worker, on_finished, on_error). PySide6 does not keep
        # a connected lambda (or the QRunnable it was created to close over)
        # alive on its own -- with nothing else referencing them, CPython's
        # refcounting GC can collect them the instant load_path() returns,
        # before the pool ever gets to run the worker on its thread. Keeping
        # this dict entry alive until the load resolves is what keeps them
        # from disappearing out from under the thread pool mid-flight.
        self._pending_loads: dict[int, tuple] = {}

        self.open_button = QPushButton("Open CSV...")
        self.path_label = QLabel("No file loaded")
        self.path_label.setWordWrap(True)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.column_list = DraggableColumnList()

        layout = QVBoxLayout(self)
        layout.addWidget(self.open_button)
        layout.addWidget(self.path_label)
        layout.addWidget(QLabel("Columns: (Ctrl+F to search)"))
        layout.addWidget(self.column_list, stretch=1)
        layout.addWidget(self.status_label)

        self.open_button.clicked.connect(self._on_open_clicked)

        search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        search_shortcut.activated.connect(self._open_search_popup)

    def _open_search_popup(self) -> None:
        if self._search_popup is None:
            self._search_popup = ColumnSearchPopup(self.column_list, self)
        self._search_popup.show()
        self._search_popup.raise_()
        self._search_popup.activateWindow()

    def _on_open_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv);;All Files (*)")
        if path:
            self.load_path(path)

    def _confirm_memory_headroom(self, path: str) -> bool:
        """Warn (with a chance to back out) before a load that looks likely
        to exceed available RAM, rather than silently attempting it and
        potentially hanging the whole machine with no warning at all.

        Fails open: if the file size or the system memory query can't be
        read for any reason, this doesn't block the load.
        """
        try:
            file_size = os.path.getsize(path)
            # .available (not .free) already accounts for memory the OS
            # could readily reclaim from its own disk cache, so it's a
            # realistic "usable" figure rather than an overly pessimistic one.
            available = psutil.virtual_memory().available
        except (OSError, psutil.Error):
            return True

        estimated_need = file_size * _MEMORY_WARNING_MULTIPLIER
        if estimated_need <= available:
            return True

        reply = QMessageBox.warning(
            self,
            "Large file warning",
            f"This CSV is {file_size / 1e9:.1f} GB and may need approximately "
            f"{estimated_need / 1e9:.1f} GB of RAM to load, but only "
            f"{available / 1e9:.1f} GB is currently available.\n\n"
            "Loading it anyway may make your computer unresponsive.\n\n"
            "Load anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def load_path(self, path: str) -> None:
        self.path_label.setText(path)
        self.status_label.setText("Reading columns...")
        self.column_list.clear()

        try:
            names = peek_schema(path)
        except Exception as exc:
            self.status_label.setText(f"Failed to read header: {exc}")
            return

        for name in names:
            self.column_list.addItem(QListWidgetItem(name))

        if not self._confirm_memory_headroom(path):
            self.status_label.setText("Load canceled -- file too large for available memory")
            return

        # The column list above is populated immediately, but series can't be
        # dropped onto a subplot until the full column data has been parsed
        # (there's nothing to plot yet) -- so a large file makes the app look
        # briefly unresponsive to a drop with no feedback. Surface that wait
        # explicitly with a busy dialog instead. No cancel button: polars'
        # read_csv is one blocking call with no interruption point, so there
        # was never a way to actually stop the parse -- only to hide the
        # dialog and discard its result, which just hid the wait without
        # shortening it.
        if self._progress is not None:
            self._progress.hide()
        self._load_generation += 1
        generation = self._load_generation

        self._progress = QProgressDialog("Loading CSV data...", None, 0, 0, self)
        self._progress.setWindowTitle("Loading CSV")
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.show()

        self.status_label.setText("Loading data in background...")
        worker = CallableWorker(lambda: load_csv(path))

        def on_finished(store: ColumnStore, g: int = generation) -> None:
            self._on_load_finished(g, store)

        def on_error(message: str, g: int = generation) -> None:
            self._on_load_error(g, message)

        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(on_error)
        # See _pending_loads' docstring: this is what keeps worker/on_finished/
        # on_error from being garbage-collected out from under the thread pool.
        self._pending_loads[generation] = (worker, on_finished, on_error)
        self._pool.start(worker)

    def _on_load_finished(self, generation: int, store: ColumnStore) -> None:
        self._pending_loads.pop(generation, None)
        if generation != self._load_generation:
            return
        if self._progress is not None:
            self._progress.hide()
        data_mb = store.total_nbytes() / (1024 * 1024)
        self.status_label.setText(
            f"Loaded {store.row_count:,} rows in {store.load_time_ms:.0f} ms ({data_mb:,.0f} MB in memory)"
        )
        self.csv_loaded.emit(store)

    def _on_load_error(self, generation: int, message: str) -> None:
        self._pending_loads.pop(generation, None)
        if generation != self._load_generation:
            return
        if self._progress is not None:
            self._progress.hide()
        self.status_label.setText(f"Load failed: {message}")
