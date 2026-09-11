from __future__ import annotations

import os
import uuid
from pathlib import Path

import psutil
from PySide6.QtCore import QMimeData, QThreadPool, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QDrag, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from csv_plot_maker.data.column_store import ColumnStore
from csv_plot_maker.data.loader import load_csv, peek_schema
from csv_plot_maker.models.data_source import DataSource, color_for_index
from csv_plot_maker.ui.header_trim_dialog import HeaderTrimDialog
from csv_plot_maker.ui.header_trim_settings import load_default_keywords
from csv_plot_maker.utils.workers import CallableWorker

# How many times a CSV's on-disk size a full load might need in RAM at peak,
# even after loader.py's own memory-reduction steps (skipping non-numeric
# columns, releasing polars' own copy of each column as it converts) --
# polars' CSV parser itself still uses working buffers beyond the final
# DataFrame, and numeric text doesn't map 1:1 to its binary size. Deliberately
# conservative: a false-positive warning costs the user two clicks, a false
# negative can hang their whole machine.
_MEMORY_WARNING_MULTIPLIER = 2.0

# Column rows carry which open file they belong to under this role; group-
# header rows leave it unset (None) -- used to tell the two kinds of row
# apart, e.g. to exclude headers from Ctrl+F matches.
_SOURCE_ID_ROLE = Qt.ItemDataRole.UserRole
# Header rows carry their own source_id under this second role instead, so a
# header can still be found/removed by source_id without being confused with
# a column row (whose _SOURCE_ID_ROLE is the same value, but on a selectable,
# draggable item).
_HEADER_SOURCE_ID_ROLE = Qt.ItemDataRole.UserRole + 1


class DraggableColumnList(QListWidget):
    """Column list grouped by source file: a bold, unselectable header row
    per open CSV, followed by that file's own columns.

    Shift-click selects a contiguous range, Ctrl-click toggles individual
    columns in/out of the selection (both native to ExtendedSelection mode,
    and naturally skip header rows since those have selection disabled), and
    dragging the selection onto a subplot in the plot grid adds all of them
    as Y series there in one drop, instead of hunting for each one in a
    combo box one at a time.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.SelectAll):
            # Ctrl+A select-all lives on the subplot's own series list
            # instead (SeriesListWidget) -- swallow it here rather than
            # falling through to Qt's own default select-all behavior,
            # which ExtendedSelection provides for free.
            return
        super().keyPressEvent(event)

    def startDrag(self, supportedActions) -> None:
        items = self.selectedItems()
        if not items:
            return
        mime = QMimeData()
        # One "source_id\tcolumn_name" pair per line -- the drop target
        # (PlotGridWidget) needs to know which file each column came from,
        # since the same column name can exist in more than one open file.
        mime.setText("\n".join(f"{item.data(_SOURCE_ID_ROLE)}\t{item.text()}" for item in items))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

    def set_source_group(self, source: DataSource, column_names: list[str]) -> None:
        """(Re)place one source's header + column rows in place, leaving
        every other source's rows untouched -- used both for a brand-new
        file and for reloading an already-open one (e.g. Header Trimming
        keywords changed) since both cases are "this source's rows are now
        exactly these names".
        """
        self.remove_source_group(source.id)
        header = QListWidgetItem(f"▾ {source.label}")
        header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsDragEnabled)
        font = header.font()
        font.setBold(True)
        header.setFont(font)
        header.setBackground(QColor(source.color))
        header.setData(_HEADER_SOURCE_ID_ROLE, source.id)
        self.addItem(header)
        for name in column_names:
            item = QListWidgetItem(name)
            item.setData(_SOURCE_ID_ROLE, source.id)
            item.setBackground(QColor(source.color))
            self.addItem(item)

    def remove_source_group(self, source_id: str) -> None:
        """Remove a source's header row and every column row under it."""
        row = 0
        while row < self.count():
            item = self.item(row)
            belongs_to_source = item.data(_SOURCE_ID_ROLE) == source_id or item.data(_HEADER_SOURCE_ID_ROLE) == source_id
            if belongs_to_source:
                self.takeItem(row)
            else:
                row += 1

    def rename_source_header(self, source_id: str, new_label: str) -> None:
        """Update just a source's header row text/color -- its column rows
        (and their order) are left untouched, unlike set_source_group()'s
        full remove-and-rebuild.
        """
        for row in range(self.count()):
            item = self.item(row)
            if item.data(_HEADER_SOURCE_ID_ROLE) == source_id:
                item.setText(f"▾ {new_label}")
                return

    def set_group_chrome_visible(self, source_id: str, source_color: str, visible: bool) -> None:
        """Show or hide the multi-file "which file is this" chrome (the
        header row's file name, and the color tint on its column rows) for
        one source -- with only one file open there's nothing to tell apart,
        so it's hidden and the list looks exactly like it did before
        multi-CSV support existed; a second file open makes it reappear.
        """
        brush = QColor(source_color) if visible else QBrush()
        for row in range(self.count()):
            item = self.item(row)
            if item.data(_HEADER_SOURCE_ID_ROLE) == source_id:
                item.setHidden(not visible)
            elif item.data(_SOURCE_ID_ROLE) == source_id:
                item.setBackground(brush)


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
            if text
            and self._list.item(row).data(_SOURCE_ID_ROLE) is not None  # skip group-header rows
            and text.lower() in self._list.item(row).text().lower()
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
    """Data tab: open one or more CSVs, show their columns immediately
    (grouped per file), load each file's full data in the background."""

    csv_loaded = Signal(object)  # emits a DataSource once its background load finishes
    csv_closed = Signal(str)  # source_id of a file the user closed
    all_files_closed = Signal()  # every open file was closed at once (Close All Files)
    source_renamed = Signal(str)  # source_id whose nickname (label) changed

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._search_popup: ColumnSearchPopup | None = None
        self._progress: QProgressDialog | None = None
        self._sources: dict[str, DataSource] = {}
        # source_id -> latest generation number for that source's load, so a
        # stale worker signal from a superseded load (Header Trimming
        # keywords changed again before the previous reload finished) can be
        # told apart from the one currently in flight for that same source.
        self._pending_generation: dict[str, int] = {}
        # (source_id, generation) -> (worker, on_finished, on_error). PySide6
        # does not keep a connected lambda (or the QRunnable it was created
        # to close over) alive on its own -- with nothing else referencing
        # them, CPython's refcounting GC can collect them the instant
        # load_path() returns, before the pool ever gets to run the worker on
        # its thread. Keeping this dict entry alive until the load resolves
        # is what keeps them from disappearing out from under the thread pool
        # mid-flight.
        self._pending_loads: dict[tuple[str, int], tuple] = {}
        # This session's active keyword list -- seeded once from the default
        # file next to the app (if one exists), then only ever changed by
        # the user explicitly editing/loading it in the Header Trimming
        # dialog. Never auto-written back to disk; see HeaderTrimDialog.
        self._header_trim_keywords: list[str] = load_default_keywords()

        self.open_button = QPushButton("Open CSV...")
        self.header_trim_button = QPushButton("Header Trimming")
        self.close_all_button = QPushButton("Close All Files")
        self.path_label = QLabel("No file loaded")
        self.path_label.setWordWrap(True)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.column_list = DraggableColumnList()
        self.column_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        top_row = QVBoxLayout()
        top_row.addWidget(self.open_button)
        top_row.addWidget(self.header_trim_button)
        top_row.addWidget(self.close_all_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self.path_label)
        layout.addWidget(QLabel("Columns: (Ctrl+F to search, right-click a file to close it)"))
        layout.addWidget(self.column_list, stretch=1)
        layout.addWidget(self.status_label)

        self.open_button.clicked.connect(self._on_open_clicked)
        self.header_trim_button.clicked.connect(self._on_header_trim_clicked)
        self.close_all_button.clicked.connect(self._on_close_all_clicked)
        self.column_list.customContextMenuRequested.connect(self._on_column_list_context_menu)

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

    def _on_header_trim_clicked(self) -> None:
        dialog = HeaderTrimDialog(self._header_trim_keywords, self)
        dialog.exec()
        new_keywords = dialog.current_keywords()
        if new_keywords == self._header_trim_keywords:
            return
        self._header_trim_keywords = new_keywords
        # Re-run every currently open file's load with the new keyword list
        # so they all pick up the change immediately, rather than leaving
        # stale (untrimmed) column names on screen until each is manually
        # reopened.
        for source in list(self._sources.values()):
            self.load_path(source.path, source_id=source.id)

    def _on_column_list_context_menu(self, pos) -> None:
        item = self.column_list.itemAt(pos)
        if item is None:
            return
        source_id = item.data(_SOURCE_ID_ROLE) or item.data(_HEADER_SOURCE_ID_ROLE)
        if source_id is None or source_id not in self._sources:
            return
        label = self._sources[source_id].label
        menu = QMenu(self)
        rename_action = menu.addAction(f'Rename "{label}"...')
        close_action = menu.addAction(f'Close "{label}"')
        chosen = menu.exec(self.column_list.mapToGlobal(pos))
        if chosen is close_action:
            self.close_source(source_id)
        elif chosen is rename_action:
            self._rename_source(source_id)

    def _rename_source(self, source_id: str) -> None:
        source = self._sources.get(source_id)
        if source is None:
            return
        new_label, ok = QInputDialog.getText(
            self, "Rename file", "Nickname to show instead of the file name:", text=source.label
        )
        if not ok:
            return
        new_label = new_label.strip()
        if not new_label or new_label == source.label:
            return
        if any(sid != source_id and s.label == new_label for sid, s in self._sources.items()):
            QMessageBox.warning(self, "Rename failed", f'"{new_label}" is already used by another open file.')
            return
        source.label = new_label
        self.column_list.rename_source_header(source_id, new_label)
        self._refresh_path_label()
        self.source_renamed.emit(source_id)

    def close_source(self, source_id: str) -> None:
        if source_id not in self._sources:
            return
        del self._sources[source_id]
        self.column_list.remove_source_group(source_id)
        self._sync_group_chrome()
        self._refresh_path_label()
        self.csv_closed.emit(source_id)

    def _sync_group_chrome(self) -> None:
        """Show each source's file-name header/color tint once more than one
        file is open, hide it while only one is -- called after any change
        to how many files are open.
        """
        show = len(self._sources) > 1
        for source in self._sources.values():
            self.column_list.set_group_chrome_visible(source.id, source.color, show)

    def _on_close_all_clicked(self) -> None:
        if not self._sources:
            return
        names = ", ".join(s.label for s in self._sources.values())
        reply = QMessageBox.question(
            self,
            "Close all files",
            f"Close all {len(self._sources)} open file(s) ({names}) and reset the current graph?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.close_all_files()

    def close_all_files(self) -> None:
        """Close every currently open file at once and reset back to the
        same blank state as before any CSV was ever opened -- the "start
        over" action multi-CSV support otherwise has no equivalent for,
        since opening a new file now adds alongside what's already open
        instead of replacing it (see MainWindow._on_csv_loaded).
        """
        self._sources = {}
        self._pending_generation = {}
        self.column_list.clear()
        if self._progress is not None:
            self._progress.hide()
        self._refresh_path_label()
        self.status_label.setText("Closed all files")
        self.all_files_closed.emit()

    def _refresh_path_label(self) -> None:
        if not self._sources:
            self.path_label.setText("No file loaded")
        else:
            self.path_label.setText(
                "\n".join(f"{s.label}: {self._folder_display(s.path)}" for s in self._sources.values())
            )

    @staticmethod
    def _folder_display(path: str) -> str:
        """Just the name of the folder `path` lives in, not its full
        (often deeply nested and very wide) absolute path -- the file itself
        is already identified by its own nickname/label right next to this,
        so the folder is only shown as a "which copy is this" hint.
        """
        parent = Path(path).parent
        return parent.name or str(parent)

    def _make_unique_label(self, path: str) -> str:
        base = Path(path).stem
        used = {s.label for s in self._sources.values()}
        candidate = base
        n = 1
        while candidate in used:
            n += 1
            candidate = f"{base}_{n}"
        return candidate

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

    def load_path(
        self,
        path: str,
        source_id: str | None = None,
        label: str | None = None,
        color: str | None = None,
    ) -> None:
        """Load `path` as a new source, or -- when `source_id` names an
        already-open source -- reload that source in place (used when the
        Header Trimming keyword list changes) without disturbing any other
        currently open file's rows.

        `label`/`color` let a caller pin the exact identity a source should
        get (used when Load Layout re-opens a file that isn't open yet, so
        the reloaded source keeps the id/label/color recorded in that
        layout instead of getting a fresh random one).
        """
        is_reload = source_id is not None and source_id in self._sources
        if is_reload:
            source = self._sources[source_id]
            source.path = path
        else:
            if source_id is None:
                source_id = uuid.uuid4().hex
            source = DataSource(
                id=source_id,
                path=path,
                label=label or self._make_unique_label(path),
                color=color or color_for_index(len(self._sources)),
            )
            self._sources[source_id] = source

        self._refresh_path_label()
        self.status_label.setText(f"Reading columns for {source.label}...")

        header_trim_keywords = self._header_trim_keywords

        try:
            names = peek_schema(path, header_trim_keywords)
        except Exception as exc:
            self.status_label.setText(f"Failed to read header: {exc}")
            return

        self.column_list.set_source_group(source, names)
        self._sync_group_chrome()

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
        generation = self._pending_generation.get(source_id, 0) + 1
        self._pending_generation[source_id] = generation

        self._progress = QProgressDialog(f"Loading {source.label}...", None, 0, 0, self)
        self._progress.setWindowTitle("Loading CSV")
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.show()

        self.status_label.setText(f"Loading {source.label} in background...")
        worker = CallableWorker(lambda: load_csv(path, header_trim_keywords))

        def on_finished(store: ColumnStore, sid: str = source_id, g: int = generation) -> None:
            self._on_load_finished(sid, g, store)

        def on_error(message: str, sid: str = source_id, g: int = generation) -> None:
            self._on_load_error(sid, g, message)

        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(on_error)
        # See _pending_loads' docstring: this is what keeps worker/on_finished/
        # on_error from being garbage-collected out from under the thread pool.
        self._pending_loads[(source_id, generation)] = (worker, on_finished, on_error)
        self._pool.start(worker)

    def _on_load_finished(self, source_id: str, generation: int, store: ColumnStore) -> None:
        self._pending_loads.pop((source_id, generation), None)
        if generation != self._pending_generation.get(source_id):
            return
        if self._progress is not None:
            self._progress.hide()
        source = self._sources.get(source_id)
        if source is None:
            return
        source.store = store
        data_mb = store.total_nbytes() / (1024 * 1024)
        self.status_label.setText(
            f"Loaded {source.label}: {store.row_count:,} rows in {store.load_time_ms:.0f} ms ({data_mb:,.0f} MB in memory)"
        )
        self.csv_loaded.emit(source)

    def _on_load_error(self, source_id: str, generation: int, message: str) -> None:
        self._pending_loads.pop((source_id, generation), None)
        if generation != self._pending_generation.get(source_id):
            return
        if self._progress is not None:
            self._progress.hide()
        self.status_label.setText(f"Load failed: {message}")
        source = self._sources.get(source_id)
        if source is not None and source.store is None:
            # A brand-new file that never finished its first successful load
            # is useless to keep around -- its columns would just be dead
            # drag sources with no data behind them.
            self.close_source(source_id)
