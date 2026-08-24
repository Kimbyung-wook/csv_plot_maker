"""Manual smoke test for Phase 5 (dual Y-axis support). Run headless:

    $env:QT_QPA_PLATFORM = "offscreen"
    uv run python scripts/smoke_test_dual_axis.py
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from csv_plot_maker.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()

    w.csv_panel.load_path("tests/fixtures/small.csv")
    loop = QEventLoop()
    QTimer.singleShot(1000, loop.quit)
    loop.exec()

    w._on_series_add_requested("a")
    w._on_series_add_requested("b")

    view = w._active_view()
    subplot = w._active_subplot()
    series_a, series_b = subplot.series

    print("right axis hidden before any secondary series:", not view.plot_item.getAxis("right").isVisible())

    # select series_a via the real widget and flip it to the secondary axis
    w.series_panel.series_list.setCurrentRow(0)
    app.processEvents()
    print("axis combo enabled on selection:", w.series_panel.axis_combo.isEnabled())

    idx_secondary = w.series_panel.axis_combo.findData("secondary")
    w.series_panel.axis_combo.setCurrentIndex(idx_secondary)
    app.processEvents()

    print("series_a.axis after switch:", series_a.axis)
    print("curve still tracked:", series_a.id in view._curves)
    print("curve routed to right_vb:", series_a.id in [
        item for item in [view._curves[series_a.id]] if item.getViewBox() is view.right_vb
    ] != [])
    print("right axis now visible:", view.plot_item.getAxis("right").isVisible())

    # selection should have been restored to series_a after the list refresh
    print("selection restored after axis switch:", w._selected_series_id == series_a.id)

    curve_a = view._curves[series_a.id]
    xa, ya = curve_a.getData()
    print("series_a data intact after axis move:", list(xa) == [0.0, 1.0, 2.0])

    # series_b stays on primary; verify both curves coexist independently
    print("series_b still on primary:", series_b.axis == "primary")
    curve_b = view._curves[series_b.id]
    print("primary curve view box:", curve_b.getViewBox() is view.plot_item.vb)

    # switch back to primary and confirm right axis auto-hides again
    w.series_panel.series_list.setCurrentRow(0)
    app.processEvents()
    idx_primary = w.series_panel.axis_combo.findData("primary")
    w.series_panel.axis_combo.setCurrentIndex(idx_primary)
    app.processEvents()
    print("right axis hidden again after moving series back:", not view.plot_item.getAxis("right").isVisible())

    # remove series_a, then re-check clean state
    w._on_series_remove_requested(series_a.id)
    print("series_a curve removed:", series_a.id not in view._curves)


if __name__ == "__main__":
    main()
