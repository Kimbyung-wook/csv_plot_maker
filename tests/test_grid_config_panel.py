from csv_plot_maker.ui.grid_config_panel import GridConfigPanel


def test_dims_changed_emits_current_spin_values(qtbot):
    panel = GridConfigPanel()
    qtbot.addWidget(panel)

    with qtbot.waitSignal(panel.grid_dims_changed) as blocker:
        panel.rows_spin.setValue(2)

    assert blocker.args == [2, 1]

    with qtbot.waitSignal(panel.grid_dims_changed) as blocker:
        panel.cols_spin.setValue(3)

    assert blocker.args == [2, 3]


def test_set_subplot_options_and_set_active_do_not_reemit_active_subplot_changed(qtbot):
    # blockSignals around both calls -- population is not itself a user
    # pick, so it must not look like one to a listener.
    panel = GridConfigPanel()
    qtbot.addWidget(panel)
    received = []
    panel.active_subplot_changed.connect(received.append)

    panel.set_subplot_options([("a", "(0, 0)"), ("b", "(0, 1)")])
    panel.set_active("b")

    assert received == []
    assert panel.active_combo.currentData() == "b"


def test_selecting_a_subplot_from_the_combo_emits_its_id(qtbot):
    panel = GridConfigPanel()
    qtbot.addWidget(panel)
    panel.set_subplot_options([("a", "(0, 0)"), ("b", "(0, 1)")])

    with qtbot.waitSignal(panel.active_subplot_changed) as blocker:
        panel.active_combo.setCurrentIndex(1)

    assert blocker.args == ["b"]


def test_sync_grid_spins_does_not_reemit_dims_changed(qtbot):
    panel = GridConfigPanel()
    qtbot.addWidget(panel)
    received = []
    panel.grid_dims_changed.connect(lambda r, c: received.append((r, c)))

    panel.sync_grid_spins(2, 3)

    assert received == []
    assert (panel.rows_spin.value(), panel.cols_spin.value()) == (2, 3)


def test_clear_buttons_emit_their_requests(qtbot):
    panel = GridConfigPanel()
    qtbot.addWidget(panel)

    with qtbot.waitSignal(panel.clear_subplot_requested):
        panel.clear_subplot_button.click()

    with qtbot.waitSignal(panel.clear_all_requested):
        panel.clear_all_button.click()
