from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QStyleHints
from PySide6.QtWidgets import QApplication

from csv_plot_maker.ui import theme


def test_apply_app_theme_only_sets_style_once(qtbot):
    app = QApplication.instance()

    # Reset to a known non-Fusion style so the first call is guaranteed to
    # actually need to apply it.
    app.setStyle("Fusion")
    original = app.style()

    with patch.object(QApplication, "setStyle", wraps=QApplication.setStyle) as mock_set_style:
        # Re-calling setStyle("Fusion") on every theme switch is redundant
        # once the style is already Fusion, and was found to crash the
        # process outright on a large/complex pyqtgraph scene under real
        # rendering -- see theme.apply_app_theme's comment. Repeated theme
        # switches must not re-invoke setStyle after the first time.
        theme.apply_app_theme(app, "dark")
        theme.apply_app_theme(app, "light")
        theme.apply_app_theme(app, "dark")
        assert mock_set_style.call_count == 0

    del original


def test_apply_app_theme_still_applies_style_when_not_fusion():
    app = QApplication.instance()
    app.setStyle(app.style().objectName())  # no-op; ensure app has *a* style

    with patch.object(QApplication, "style", return_value=_FakeStyle("windows")):
        with patch.object(QApplication, "setStyle") as mock_set_style:
            theme.apply_app_theme(app, "light")
            mock_set_style.assert_called_once_with("Fusion")


def test_apply_app_theme_pins_qt_color_scheme_to_the_forced_mode(qtbot):
    # Since Qt 6.5, some Qt/OS chrome (native dialogs, Windows' dark title
    # bar, Fusion's own paint-time accents) can react to
    # styleHints().colorScheme() independently of the QPalette this function
    # also sets -- forcing Light/Dark must pin this too, or that chrome can
    # keep following a stale OS-reported scheme while the rest of the app
    # (and this app's own plot colors) already switched.
    #
    # Asserted via the call itself (not the resulting colorScheme() value):
    # the offscreen QPA platform used for headless tests doesn't actually
    # support overriding colorScheme() at all -- it silently stays Unknown
    # regardless -- so only a real platform plugin can prove the *effect*;
    # this proves the app requests it.
    app = QApplication.instance()

    with patch.object(QStyleHints, "setColorScheme") as mock_set_scheme:
        theme.apply_app_theme(app, "dark")
        mock_set_scheme.assert_called_once_with(Qt.ColorScheme.Dark)

    with patch.object(QStyleHints, "setColorScheme") as mock_set_scheme:
        theme.apply_app_theme(app, "light")
        mock_set_scheme.assert_called_once_with(Qt.ColorScheme.Light)


def test_system_mode_releases_any_previously_forced_scheme_before_resolving(qtbot):
    # Forcing "dark" pins styleHints().colorScheme() to Dark (see above).
    # Selecting "System" afterward must release that override *before*
    # resolve_mode() reads it, or "system" would be stuck reading back
    # whatever this function itself last forced instead of the OS's actual
    # current setting.
    app = QApplication.instance()

    with patch.object(QStyleHints, "setColorScheme") as mock_set_scheme:
        theme.apply_app_theme(app, "system")
        # Called twice: once to release (Unknown) before resolving, once
        # more to (re-)pin the hint to whatever "system" just resolved to.
        assert mock_set_scheme.call_args_list[0].args == (Qt.ColorScheme.Unknown,)


class _FakeStyle:
    def __init__(self, name: str) -> None:
        self._name = name

    def objectName(self) -> str:
        return self._name

    def standardPalette(self):
        from PySide6.QtGui import QPalette

        return QPalette()
