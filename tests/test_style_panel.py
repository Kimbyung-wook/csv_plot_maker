from csv_plot_maker.models.series import Series
from csv_plot_maker.ui.style_panel import StylePanel


def _clear_and_commit(spin_box) -> None:
    """Simulate the user selecting all text, deleting it, then moving focus
    away (or pressing Enter) before typing a replacement -- the scenario
    that used to silently revert to whatever value was there before.
    """
    spin_box.lineEdit().setText("")
    spin_box.interpretText()


def test_clearing_scale_field_resets_to_default_one_not_the_previous_value(qtbot):
    panel = StylePanel()
    qtbot.addWidget(panel)
    panel.set_series(Series(y_column="a", scale=3.5), series_count=1)

    _clear_and_commit(panel.scale_spin)

    assert panel.scale_spin.value() == 1.0


def test_clearing_offset_field_resets_to_default_zero_not_the_previous_value(qtbot):
    panel = StylePanel()
    qtbot.addWidget(panel)
    panel.set_series(Series(y_column="a", offset=42.0), series_count=1)

    _clear_and_commit(panel.offset_spin)

    assert panel.offset_spin.value() == 0.0


def test_clearing_x_offset_field_resets_to_default_zero_not_the_previous_value(qtbot):
    panel = StylePanel()
    qtbot.addWidget(panel)
    panel.set_series(Series(y_column="a", x_column="t", x_offset=42.0), series_count=1)

    _clear_and_commit(panel.x_offset_spin)

    assert panel.x_offset_spin.value() == 0.0


def test_x_offset_spin_emits_x_offset_changed(qtbot):
    panel = StylePanel()
    qtbot.addWidget(panel)

    received = []
    panel.x_offset_changed.connect(received.append)

    panel.x_offset_spin.setValue(12.5)

    assert received == [12.5]


def test_zero_at_start_button_emits_request(qtbot):
    panel = StylePanel()
    qtbot.addWidget(panel)

    received = []
    panel.zero_at_start_requested.connect(lambda: received.append(True))

    panel.zero_at_start_button.click()

    assert received == [True]


def test_apply_x_to_matching_button_emits_request(qtbot):
    panel = StylePanel()
    qtbot.addWidget(panel)

    received = []
    panel.apply_x_to_matching_requested.connect(lambda: received.append(True))

    panel.apply_x_to_matching_button.click()

    assert received == [True]


def test_set_x_offset_updates_spin_without_emitting(qtbot):
    panel = StylePanel()
    qtbot.addWidget(panel)

    received = []
    panel.x_offset_changed.connect(received.append)

    panel.set_x_offset(-3.0)

    assert panel.x_offset_spin.value() == -3.0
    assert received == []


def test_set_series_populates_x_combo_scoped_to_one_series_own_file(qtbot):
    panel = StylePanel()
    qtbot.addWidget(panel)

    panel.set_series(Series(y_column="a", x_column="timestamp"), series_count=1, x_options=["timestamp", "Sequential"])

    assert panel.x_combo.currentText() == "timestamp"
    assert [panel.x_combo.itemText(i) for i in range(panel.x_combo.count())] == ["timestamp", "Sequential"]


def test_x_column_changed_emits_the_selected_column_name(qtbot):
    panel = StylePanel()
    qtbot.addWidget(panel)
    panel.set_series(Series(y_column="a", x_column="timestamp"), series_count=1, x_options=["timestamp", "Sequential"])

    received = []
    panel.x_column_changed.connect(received.append)
    panel.x_combo.setCurrentText("Sequential")

    assert received == ["Sequential"]
