from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

LIGHT_PLOT_BACKGROUND = "w"
LIGHT_PLOT_FOREGROUND = "k"
DARK_PLOT_BACKGROUND = "#191919"
DARK_PLOT_FOREGROUND = "#d0d0d0"


def _dark_palette() -> QPalette:
    palette = QPalette()
    window = QColor(53, 53, 53)
    base = QColor(35, 35, 35)
    text = QColor(220, 220, 220)
    highlight = QColor(42, 130, 218)

    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, window)
    palette.setColor(QPalette.ColorRole.ToolTipBase, text)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, window)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 80, 80))
    palette.setColor(QPalette.ColorRole.Link, highlight)
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, base)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(127, 127, 127))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(127, 127, 127))
    return palette


def resolve_mode(mode: str) -> str:
    """Resolve "system" to "light"/"dark" via Qt's OS color-scheme query."""
    if mode != "system":
        return mode
    app = QApplication.instance()
    try:
        if app is not None and app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
            return "dark"
    except Exception:
        pass
    return "light"


def apply_app_theme(app: QApplication, mode: str) -> tuple[str, str]:
    """Apply "light"/"dark"/"system" to the app palette.

    pyqtgraph plots don't follow QPalette, so this returns the
    (background, foreground) colors the caller should push into the plot
    grid separately (PlotGridWidget.set_theme_colors).
    """
    resolved = resolve_mode(mode)
    app.setStyle("Fusion")
    if resolved == "dark":
        app.setPalette(_dark_palette())
        return DARK_PLOT_BACKGROUND, DARK_PLOT_FOREGROUND
    app.setPalette(app.style().standardPalette())
    return LIGHT_PLOT_BACKGROUND, LIGHT_PLOT_FOREGROUND
