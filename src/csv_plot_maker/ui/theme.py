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
    if mode == "system":
        # Release any color-scheme override an earlier explicit Light/Dark
        # selection left behind (see below) *before* resolving, so
        # resolve_mode() reads the OS's actual current setting again instead
        # of whatever this function last forced it to.
        try:
            app.styleHints().setColorScheme(Qt.ColorScheme.Unknown)
        except Exception:
            pass
    resolved = resolve_mode(mode)
    # Only apply the style once, ever -- re-calling QApplication.setStyle()
    # with the *same* style on every theme switch is redundant (only the
    # palette actually needs to change between light/dark), and doing it
    # repeatedly against a large, complex pyqtgraph scene (many subplots,
    # each with several AxisItems/ViewBoxes) has been observed to crash the
    # process outright (Windows access violation) on the second or later
    # switch, under real (non-offscreen) rendering. Skipping the redundant
    # re-application avoids the crash entirely without losing anything --
    # the style was already "Fusion" from the first call.
    if app.style().objectName().lower() != "fusion":
        app.setStyle("Fusion")
    # Explicitly pin Qt's own notion of the *current* color scheme to
    # whatever we just resolved, rather than leaving it tracking the OS
    # setting. Since Qt 6.5, Fusion (and some native dialogs/window chrome,
    # e.g. Windows' dark title bar) can react to
    # QGuiApplication.styleHints().colorScheme() on its own, independently of
    # the QPalette we set below -- if that hint still says "the OS is dark"
    # while the user forced Light mode here, only the pieces of the UI that
    # strictly follow our explicit QPalette (like this app's own plot colors,
    # pushed separately via PlotGridWidget.set_theme_colors) reliably match
    # the forced mode, while anything Qt derives from the stale hint doesn't.
    # Pinning this removes that disagreement instead of leaving it to chance.
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark if resolved == "dark" else Qt.ColorScheme.Light)
    except Exception:
        pass
    if resolved == "dark":
        app.setPalette(_dark_palette())
        return DARK_PLOT_BACKGROUND, DARK_PLOT_FOREGROUND
    app.setPalette(app.style().standardPalette())
    return LIGHT_PLOT_BACKGROUND, LIGHT_PLOT_FOREGROUND
