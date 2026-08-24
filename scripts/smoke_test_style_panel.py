"""Manual smoke test for Phase 4 (style panel wiring). Run headless:

    $env:QT_QPA_PLATFORM = "offscreen"
    uv run python scripts/smoke_test_style_panel.py
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

    w.series_panel.series_list.setCurrentRow(0)
    app.processEvents()

    print("selected series id set:", bool(w._selected_series_id))
    print("style panel enabled:", w.style_panel.isEnabled())

    subplot = w._active_subplot()
    series = subplot.get_series(w._selected_series_id)
    print("series before style change:", series.color, series.line_style, series.width)

    view = w._active_view()
    curve = view._curves[series.id]
    x_before, y_before = curve.getData()

    w.style_panel.line_style_combo.setCurrentText("dash")
    w.style_panel.width_spin.setValue(4.0)
    w.style_panel.marker_combo.setCurrentText("Circle")
    app.processEvents()

    print("series after style change:", series.line_style, series.width, series.marker)

    x_after, y_after = curve.getData()
    print(
        "data unchanged after style-only edit:",
        list(x_after) == list(x_before) and list(y_after) == list(y_before),
    )
    print("curve pen width matches:", curve.opts["pen"].widthF())

    w.series_panel.series_list.setCurrentRow(1)
    app.processEvents()
    series2 = subplot.get_series(w._selected_series_id)
    print("second series id differs:", series2.id != series.id)
    print("style panel shows second series width (expect default 1.5):", w.style_panel.width_spin.value())

    w._refresh_series_list()
    print("style panel disabled after list refresh:", not w.style_panel.isEnabled())


if __name__ == "__main__":
    main()
