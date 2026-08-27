from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SeriesListWidget(QListWidget):
    """Y-series list that also deletes the current row on Delete/Backspace."""

    delete_requested = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.currentItem() is not None:
            self.delete_requested.emit()
            return
        super().keyPressEvent(event)


class SeriesPanel(QWidget):
    """Middle of the merged config panel: the active subplot's X column and Y series.

    Series are no longer added here via a combo+button -- drag a column from
    the Data tab onto a subplot in the plot grid instead. This panel just
    lists what's already there and reports selection so the style section
    below can edit it. The selected series can also be removed with the
    Delete key, not just the Style section's Remove Series button.

    Duplicate column selection is allowed by design: series are identified by
    a generated id, not by column name, so the same Y column can be added
    more than once (e.g. with different styles).
    """

    x_column_changed = Signal(str)
    x_offset_changed = Signal(float)
    zero_at_start_requested = Signal()
    apply_x_to_all_requested = Signal()
    series_selection_changed = Signal(str)  # series id, "" when nothing selected
    series_delete_requested = Signal(str)  # series id
    legend_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.x_combo = QComboBox()
        self.x_offset_spin = QDoubleSpinBox()
        self.x_offset_spin.setRange(-1e12, 1e12)
        self.x_offset_spin.setDecimals(3)
        self.zero_at_start_button = QPushButton("Zero at start")
        self.apply_x_to_all_button = QPushButton("Apply X Column && Offset to All Subplots")
        self.series_list = SeriesListWidget()
        self.legend_checkbox = QCheckBox("Show Legend")
        self.legend_checkbox.setChecked(True)

        offset_layout = QHBoxLayout()
        offset_layout.addWidget(QLabel("X offset:"))
        offset_layout.addWidget(self.x_offset_spin, 1)
        offset_layout.addWidget(self.zero_at_start_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("X column:"))
        layout.addWidget(self.x_combo)
        layout.addLayout(offset_layout)
        layout.addWidget(self.apply_x_to_all_button)
        layout.addWidget(self.legend_checkbox)

        layout.addWidget(QLabel("Y series in this subplot:"))
        layout.addWidget(self.series_list, 1)

        self.x_combo.currentTextChanged.connect(self._on_x_changed)
        self.x_offset_spin.valueChanged.connect(self.x_offset_changed)
        self.zero_at_start_button.clicked.connect(self.zero_at_start_requested)
        self.apply_x_to_all_button.clicked.connect(self.apply_x_to_all_requested)
        self.series_list.currentItemChanged.connect(self._on_selection_changed)
        self.series_list.delete_requested.connect(self._on_delete_requested)
        self.legend_checkbox.toggled.connect(self.legend_toggled)

    def set_columns(self, names: list[str]) -> None:
        current = self.x_combo.currentText()
        self.x_combo.blockSignals(True)
        self.x_combo.clear()
        self.x_combo.addItems(names)
        if current in names:
            self.x_combo.setCurrentText(current)
        self.x_combo.blockSignals(False)

    def set_x_column(self, name: str | None) -> None:
        if name:
            self.x_combo.blockSignals(True)
            self.x_combo.setCurrentText(name)
            self.x_combo.blockSignals(False)

    def set_x_offset(self, value: float) -> None:
        self.x_offset_spin.blockSignals(True)
        self.x_offset_spin.setValue(value)
        self.x_offset_spin.blockSignals(False)

    def set_show_legend(self, visible: bool) -> None:
        self.legend_checkbox.blockSignals(True)
        self.legend_checkbox.setChecked(visible)
        self.legend_checkbox.blockSignals(False)

    def refresh_series_list(self, series_items: list[tuple[str, str]]) -> None:
        """series_items: list of (series_id, display_text)."""
        self.series_list.blockSignals(True)
        self.series_list.clear()
        for series_id, text in series_items:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, series_id)
            self.series_list.addItem(item)
        self.series_list.blockSignals(False)

    def select_series_id(self, series_id: str) -> None:
        for row in range(self.series_list.count()):
            item = self.series_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == series_id:
                self.series_list.setCurrentRow(row)
                return

    def selected_series_id(self) -> str:
        item = self.series_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def _on_x_changed(self, name: str) -> None:
        if name:
            self.x_column_changed.emit(name)

    def _on_selection_changed(self, current, _previous) -> None:
        series_id = current.data(Qt.ItemDataRole.UserRole) if current else ""
        self.series_selection_changed.emit(series_id or "")

    def _on_delete_requested(self) -> None:
        series_id = self.selected_series_id()
        if series_id:
            self.series_delete_requested.emit(series_id)
