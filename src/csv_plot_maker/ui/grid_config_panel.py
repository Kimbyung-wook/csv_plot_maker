from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class GridConfigPanel(QWidget):
    """Top of the merged config panel: subplot grid dimensions and the active subplot.

    Rows/Cols changes apply immediately (no Apply button) -- each spinbox edit
    fires `grid_dims_changed` directly.
    """

    grid_dims_changed = Signal(int, int)  # rows, cols
    active_subplot_changed = Signal(str)  # subplot id
    clear_subplot_requested = Signal()
    clear_all_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 6)
        self.rows_spin.setValue(1)

        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 6)
        self.cols_spin.setValue(1)

        self.active_combo = QComboBox()

        self.clear_subplot_button = QPushButton("Clear This Subplot")
        self.clear_all_button = QPushButton("Clear All Subplots")

        form = QFormLayout()
        form.addRow("Rows:", self.rows_spin)
        form.addRow("Cols:", self.cols_spin)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Active subplot:"))
        layout.addWidget(self.active_combo)

        clear_row = QHBoxLayout()
        clear_row.addWidget(self.clear_subplot_button)
        clear_row.addWidget(self.clear_all_button)
        layout.addLayout(clear_row)

        self.rows_spin.valueChanged.connect(self._on_dims_changed)
        self.cols_spin.valueChanged.connect(self._on_dims_changed)
        self.active_combo.currentIndexChanged.connect(self._on_active_changed)
        self.clear_subplot_button.clicked.connect(self.clear_subplot_requested)
        self.clear_all_button.clicked.connect(self.clear_all_requested)

    def _on_dims_changed(self, _value: int) -> None:
        self.grid_dims_changed.emit(self.rows_spin.value(), self.cols_spin.value())

    def _on_active_changed(self, index: int) -> None:
        if index < 0:
            return
        subplot_id = self.active_combo.itemData(index)
        if subplot_id:
            self.active_subplot_changed.emit(subplot_id)

    def set_subplot_options(self, options: list[tuple[str, str]]) -> None:
        """options: list of (subplot_id, label)."""
        self.active_combo.blockSignals(True)
        self.active_combo.clear()
        for subplot_id, label in options:
            self.active_combo.addItem(label, subplot_id)
        self.active_combo.blockSignals(False)

    def set_active(self, subplot_id: str) -> None:
        idx = self.active_combo.findData(subplot_id)
        if idx >= 0:
            self.active_combo.blockSignals(True)
            self.active_combo.setCurrentIndex(idx)
            self.active_combo.blockSignals(False)

    def sync_grid_spins(self, rows: int, cols: int) -> None:
        self.rows_spin.blockSignals(True)
        self.cols_spin.blockSignals(True)
        self.rows_spin.setValue(rows)
        self.cols_spin.setValue(cols)
        self.rows_spin.blockSignals(False)
        self.cols_spin.blockSignals(False)
