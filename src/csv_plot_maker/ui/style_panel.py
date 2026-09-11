from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from csv_plot_maker.models.series import Series
from csv_plot_maker.plotting.style_map import MARKER_CHOICES

LINE_STYLES = ["solid", "dash", "dot", "dashdot", "none"]


class DefaultingDoubleSpinBox(QDoubleSpinBox):
    """A QDoubleSpinBox that snaps to a fixed default instead of whatever
    value was there before editing, when the field is left in a state Qt
    can't interpret as a number (typically: cleared to blank, then focus
    moves away before a full replacement is typed).

    QAbstractSpinBox's own default (`CorrectToPreviousValue`) calls
    `fixup()` with the unparseable text in that situation and uses whatever
    string it returns -- by default just the last valid value, which reads
    as "my edit got silently undone". Returning this box's own default here
    instead makes clearing the field behave as "reset to default", not
    "revert my last change".
    """

    def __init__(self, default: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._default = default

    def fixup(self, text: str) -> str:
        return str(self._default)


class StylePanel(QWidget):
    """Bottom of the merged config panel: appears only once a Y series is selected.

    Holds live color/line-style/marker/width controls, the primary/secondary
    Y-axis assignment, the selected series' own X column/offset (X is a
    per-series property so a subplot can mix series from more than one file
    -- see Series.x_column), and the "Remove Series" action. Every control
    edit fires immediately (no Apply button) so the caller can push the new
    values to the plotted curve via a cheap setPen/setSymbol call, per the
    "dynamic line style" requirement.
    """

    style_changed = Signal()
    axis_changed = Signal(str)  # "primary" or "secondary"
    transform_changed = Signal()  # scale and/or offset edited
    x_column_changed = Signal(str)  # column name, within the series' own source
    x_offset_changed = Signal(float)
    zero_at_start_requested = Signal()
    apply_x_to_matching_requested = Signal()
    remove_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._color = "#1f77b4"
        self._updating = False
        self._updating_axis = False
        self._updating_x_column = False

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

        # transformed = raw * scale + offset, applied to this series' own Y
        # data before plotting -- e.g. unit conversion or a quick calibration
        # tweak on one already-added series, without touching the CSV.
        self.scale_spin = DefaultingDoubleSpinBox(default=1.0)
        self.scale_spin.setRange(-1e9, 1e9)
        self.scale_spin.setDecimals(6)
        self.scale_spin.setSingleStep(0.1)
        self.scale_spin.setValue(1.0)

        self.offset_spin = DefaultingDoubleSpinBox(default=0.0)
        self.offset_spin.setRange(-1e12, 1e12)
        self.offset_spin.setDecimals(3)
        self.offset_spin.setSingleStep(1.0)
        self.offset_spin.setValue(0.0)

        # This series' own X column -- always one of its own file's columns
        # (see Series.x_column), so a subplot mixing series from more than
        # one file still plots each one against data of the same length.
        self.x_combo = QComboBox()
        self.x_offset_spin = DefaultingDoubleSpinBox(default=0.0)
        self.x_offset_spin.setRange(-1e12, 1e12)
        self.x_offset_spin.setDecimals(3)
        self.zero_at_start_button = QPushButton("Zero at start")
        self.apply_x_to_matching_button = QPushButton("Set All to X column config")

        self.remove_button = QPushButton("Remove Series")

        x_offset_layout = QHBoxLayout()
        x_offset_layout.addWidget(self.x_offset_spin, 1)
        x_offset_layout.addWidget(self.zero_at_start_button)

        form = QFormLayout()
        form.addRow(self.axis_label, self.axis_combo)
        form.addRow("Color:", self.color_button)
        form.addRow("Line style:", self.line_style_combo)
        form.addRow("Marker:", self.marker_combo)
        form.addRow("Width:", self.width_spin)
        form.addRow("Scale:", self.scale_spin)
        form.addRow("Offset:", self.offset_spin)
        form.addRow("X column:", self.x_combo)
        form.addRow("X offset:", x_offset_layout)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Series style"))
        layout.addLayout(form)
        layout.addWidget(self.apply_x_to_matching_button)
        layout.addWidget(self.remove_button)

        self.axis_combo.currentIndexChanged.connect(self._on_axis_changed)
        self.color_button.clicked.connect(self._on_pick_color)
        self.line_style_combo.currentTextChanged.connect(self._emit_changed)
        self.marker_combo.currentTextChanged.connect(self._emit_changed)
        self.width_spin.valueChanged.connect(self._emit_changed)
        self.scale_spin.valueChanged.connect(self._emit_transform_changed)
        self.offset_spin.valueChanged.connect(self._emit_transform_changed)
        self.x_combo.currentTextChanged.connect(self._on_x_column_changed)
        self.x_offset_spin.valueChanged.connect(self.x_offset_changed)
        self.zero_at_start_button.clicked.connect(self.zero_at_start_requested)
        self.apply_x_to_matching_button.clicked.connect(self.apply_x_to_matching_requested)
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit())

        self.setVisible(False)  # nothing shown until a series is selected

    def _set_x_options(self, column_names: list[str]) -> None:
        self.x_combo.clear()
        self.x_combo.addItems(column_names)

    def set_x_offset(self, value: float) -> None:
        self.x_offset_spin.blockSignals(True)
        self.x_offset_spin.setValue(value)
        self.x_offset_spin.blockSignals(False)

    def set_series(self, series: Series | None, series_count: int = 0, x_options: list[str] = ()) -> None:
        """series_count: how many series the owning subplot has in total.

        `x_options`: the selected series' own file's numeric columns, so its
        current x_column can be found among them -- scoped and passed in by
        the caller together with `series` (rather than via a separate call
        the caller must remember to make first) since X must always come
        from that series' own source.

        The primary/secondary axis picker is shown once there's more than
        one series to split across axes, OR the selected series is already
        on the secondary axis (so it stays reachable/switchable even if its
        sibling series get removed later). A lone, still-primary series has
        nothing to split, so the picker stays hidden for it.
        """
        self._updating = True
        self._updating_axis = True
        self._updating_x_column = True
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
            self.scale_spin.setValue(series.scale)
            self.offset_spin.setValue(series.offset)
            idx = self.axis_combo.findData(series.axis)
            if idx >= 0:
                self.axis_combo.setCurrentIndex(idx)
            show_axis_picker = series_count > 1 or series.axis == "secondary"
            self.axis_label.setVisible(show_axis_picker)
            self.axis_combo.setVisible(show_axis_picker)
            self._set_x_options(list(x_options))
            if series.x_column:
                self.x_combo.setCurrentText(series.x_column)
            self.set_x_offset(series.x_offset)
        self._updating = False
        self._updating_axis = False
        self._updating_x_column = False

    def current_color(self) -> str:
        return self._color

    def current_line_style(self) -> str:
        return self.line_style_combo.currentText()

    def current_marker(self) -> str | None:
        return MARKER_CHOICES[self.marker_combo.currentText()]

    def current_width(self) -> float:
        return self.width_spin.value()

    def current_scale(self) -> float:
        return self.scale_spin.value()

    def current_offset(self) -> float:
        return self.offset_spin.value()

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

    def _emit_transform_changed(self, *_args) -> None:
        if not self._updating:
            self.transform_changed.emit()

    def _on_axis_changed(self, index: int) -> None:
        if self._updating_axis or index < 0:
            return
        axis = self.axis_combo.itemData(index)
        if axis:
            self.axis_changed.emit(axis)

    def _on_x_column_changed(self, text: str) -> None:
        if self._updating_x_column or not text:
            return
        self.x_column_changed.emit(text)
