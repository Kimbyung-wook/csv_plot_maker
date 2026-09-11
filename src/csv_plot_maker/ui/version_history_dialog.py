from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

from csv_plot_maker._version import VERSION_HISTORY


def _history_html() -> str:
    sections = []
    for version, date, bullets in VERSION_HISTORY:
        items = "".join(f"<li>{bullet}</li>" for bullet in bullets)
        sections.append(
            f"<h3>v{version} <span style='color:#888; font-weight:normal;'>({date})</span></h3><ul>{items}</ul>"
        )
    return f"<h2>CSV Plot Maker -- Version History</h2>{''.join(sections)}"


class VersionHistoryDialog(QDialog):
    """Info > Version History: a brief, bullet-point changelog per release."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Version History")
        self.resize(560, 480)

        browser = QTextBrowser()
        browser.setHtml(_history_html())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(browser)
        layout.addWidget(buttons)
