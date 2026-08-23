from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

from csv_plot_maker._version import BUILD_DATE, __version__

_LICENSE_HTML = f"""
<h2>CSV Plot Maker</h2>
<p>Version {__version__} (build {BUILD_DATE})</p>

<h3>Third-party libraries</h3>
<table cellpadding="4" cellspacing="0">
<tr><th align="left">Library</th><th align="left">License</th></tr>
<tr><td>PySide6 (Qt for Python)</td><td>LGPL-3.0-only</td></tr>
<tr><td>shiboken6</td><td>LGPL-3.0-only</td></tr>
<tr><td>pyqtgraph</td><td>MIT</td></tr>
<tr><td>polars</td><td>MIT</td></tr>
<tr><td>NumPy</td><td>BSD-3-Clause</td></tr>
</table>

<h3>Company / commercial use — 사내·상업적 사용 안내</h3>
<p>
<b>PySide6</b>(및 <b>shiboken6</b>)는 <b>LGPL-3.0</b> 라이선스입니다. LGPLv3는 Qt/PySide6를
<b>동적 링크(dynamic linking)</b>로 사용하는 한 사내 도구든 상업적 제품이든 소스코드를 공개하지
않고 배포할 수 있도록 허용합니다. 이 프로그램의 standalone 실행 파일은 PyInstaller의
<code>--onedir</code> 모드로 빌드되어 PySide6/Qt가 exe와 분리된 별도 파일(동적 라이브러리)로
포함되므로, 이 조건을 충족하는 방식입니다.
</p>
<p>
<b>pyqtgraph</b>(MIT), <b>polars</b>(MIT), <b>NumPy</b>(BSD-3-Clause)는 모두 허용적(permissive)
오픈소스 라이선스로, 저작권/라이선스 고지를 유지하는 것 외에 상업적·사내 사용에 대한 별도 제약이
없습니다.
</p>
<p>
이 프로그램 자체(csv-plot-maker)의 라이선스는 별도로 지정되어 있지 않습니다.
</p>
<p style="color: #888;">
<i>본 안내는 참고용 요약이며 법률 자문이 아닙니다. 조직 외부로 배포하거나 대규모로 배포할
계획이 있다면, 각 의존성(특히 PySide6의 LGPLv3 조건)의 정확한 라이선스 조건을 사내 법무팀 등을
통해 다시 확인하시길 권장합니다.</i>
</p>
"""


class LicenseDialog(QDialog):
    """Shows bundled third-party license info, with a plain-language summary
    of what LGPLv3 (PySide6/shiboken6) means for in-company or commercial use.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("License Info")
        self.resize(560, 480)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(_LICENSE_HTML)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(browser)
        layout.addWidget(buttons)
