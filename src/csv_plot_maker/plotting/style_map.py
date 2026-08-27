from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Qt

from csv_plot_maker.models.series import Series

DEFAULT_PALETTE = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
]

_QT_LINE_STYLES = {
    "solid": Qt.PenStyle.SolidLine,
    "dash": Qt.PenStyle.DashLine,
    "dot": Qt.PenStyle.DotLine,
    "dashdot": Qt.PenStyle.DashDotLine,
    "none": Qt.PenStyle.NoPen,  # no connecting line -- marker-only series
}

MARKER_CHOICES = {
    "None": None,
    "Dot": "dot",
    "Circle": "o",
    "Square": "s",
    "Triangle": "t",
    "Diamond": "d",
    "Plus": "+",
    "Cross": "x",
}

# pyqtgraph has no dedicated "small dot" symbol distinct from a regular
# circle -- "Dot" reuses the circle glyph ('o') but always renders at this
# small, fixed size regardless of line width, so it reads as a lightweight
# point marker rather than the bigger, width-scaled "Circle" option.
_DOT_PYQTGRAPH_SYMBOL = "o"
_DOT_SYMBOL_SIZE = 4


def next_default_color(index: int) -> str:
    return DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)]


def make_pen(series: Series) -> pg.QtGui.QPen:
    return pg.mkPen(color=series.color, width=series.width, style=_QT_LINE_STYLES[series.line_style])


def symbol_kwargs(series: Series) -> dict:
    if not series.marker:
        return {"symbol": None, "symbolBrush": None, "symbolPen": None, "symbolSize": 0}
    is_dot = series.marker == "dot"
    return {
        "symbol": _DOT_PYQTGRAPH_SYMBOL if is_dot else series.marker,
        "symbolBrush": series.color,
        "symbolPen": None,  # no marker outline
        "symbolSize": _DOT_SYMBOL_SIZE if is_dot else max(series.width * 3, 6),
    }
