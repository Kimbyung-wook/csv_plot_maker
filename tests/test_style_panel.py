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
