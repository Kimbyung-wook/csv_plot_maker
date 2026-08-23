from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from csv_plot_maker.models.series import Series
from csv_plot_maker.plotting.style_map import MARKER_CHOICES

LINE_STYLES = ["solid", "dash", "dot", "dashdot", "none"]


class StylePanel(QWidget):
    """Bottom of the merged config panel: appears only once a Y series is selected.

    Holds live color/line-style/marker/width controls, the primary/secondary
    Y-axis assignment, and the "Remove Series" action for the selected series.
    Every control edit fires immediately (no Apply button) so the caller can
    push the new values to the plotted curve via a cheap setPen/setSymbol
    call, per the "dynamic line style" requirement.
    """

    style_changed = Signal()
    axis_changed = Signal(str)  # "primary" or "secondary"
    remove_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._color = "#1f77b4"
        self._updating = False
        self._updating_axis = False

        self.axis_label = QLabel("Y axis:")
        self.axis_combo = QComboBox()
        self.axis_combo.addItem("Left (primary)", "primary")
        self.axis_combo.addItem("Right (secondary)", "secondary")

        self.color_button = QPushButton()
        self.color_button.setFixedWidth(60)
        self._set_button_color(self._color)

        self.line_style_combo = QComboBox()
        self.line_style_combo.addItems(LINE_STYLES)

        self.marker_combo = QComboBox()
        self.marker_combo.addItems(list(MARKER_CHOICES.keys()))

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.5, 20.0)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setValue(1.5)

        self.remove_button = QPushButton("Remove Series")

        form = QFormLayout()
        form.addRow(self.axis_label, self.axis_combo)
        form.addRow("Color:", self.color_button)
        form.addRow("Line style:", self.line_style_combo)
        form.addRow("Marker:", self.marker_combo)
        form.addRow("Width:", self.width_spin)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Series style"))
        layout.addLayout(form)
        layout.addWidget(self.remove_button)

        self.axis_combo.currentIndexChanged.connect(self._on_axis_changed)
        self.color_button.clicked.connect(self._on_pick_color)
        self.line_style_combo.currentTextChanged.connect(self._emit_changed)
        self.marker_combo.currentTextChanged.connect(self._emit_changed)
        self.width_spin.valueChanged.connect(self._emit_changed)
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit())

        self.setVisible(False)  # nothing shown until a series is selected

    def set_series(self, series: Series | None, series_count: int = 0) -> None:
        """series_count: how many series the owning subplot has in total.

        The primary/secondary axis picker is shown once there's more than
        one series to split across axes, OR the selected series is already
        on the secondary axis (so it stays reachable/switchable even if its
        sibling series get removed later). A lone, still-primary series has
        nothing to split, so the picker stays hidden for it.
        """
        self._updating = True
        self._updating_axis = True
        if series is None:
            self.setVisible(False)
        else:
            self.setVisible(True)
            self._color = series.color
            self._set_button_color(series.color)
            self.line_style_combo.setCurrentText(series.line_style)
            marker_name = next((k for k, v in MARKER_CHOICES.items() if v == series.marker), "None")
            self.marker_combo.setCurrentText(marker_name)
            self.width_spin.setValue(series.width)
            idx = self.axis_combo.findData(series.axis)
            if idx >= 0:
                self.axis_combo.setCurrentIndex(idx)
            show_axis_picker = series_count > 1 or series.axis == "secondary"
            self.axis_label.setVisible(show_axis_picker)
            self.axis_combo.setVisible(show_axis_picker)
        self._updating = False
        self._updating_axis = False

    def current_color(self) -> str:
        return self._color

    def current_line_style(self) -> str:
        return self.line_style_combo.currentText()

    def current_marker(self) -> str | None:
        return MARKER_CHOICES[self.marker_combo.currentText()]

    def current_width(self) -> float:
        return self.width_spin.value()

    def _set_button_color(self, hex_color: str) -> None:
        self.color_button.setStyleSheet(f"background-color: {hex_color};")

    def _on_pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Pick line color")
        if color.isValid():
            self._color = color.name()
            self._set_button_color(self._color)
            self._emit_changed()

    def _emit_changed(self, *_args) -> None:
        if not self._updating:
            self.style_changed.emit()

    def _on_axis_changed(self, index: int) -> None:
        if self._updating_axis or index < 0:
            return
        axis = self.axis_combo.itemData(index)
        if axis:
            self.axis_changed.emit(axis)
