from unittest.mock import patch

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


class _FakeStyle:
    def __init__(self, name: str) -> None:
        self._name = name

    def objectName(self) -> str:
        return self._name

    def standardPalette(self):
        from PySide6.QtGui import QPalette

        return QPalette()
