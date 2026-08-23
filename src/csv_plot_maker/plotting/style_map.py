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
    "Circle": "o",
    "Square": "s",
    "Triangle": "t",
    "Diamond": "d",
    "Plus": "+",
    "Cross": "x",
}


def next_default_color(index: int) -> str:
    return DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)]


def make_pen(series: Series) -> pg.QtGui.QPen:
    return pg.mkPen(color=series.color, width=series.width, style=_QT_LINE_STYLES[series.line_style])


def symbol_kwargs(series: Series) -> dict:
    if not series.marker:
        return {"symbol": None, "symbolBrush": None, "symbolPen": None, "symbolSize": 0}
    return {
        "symbol": series.marker,
        "symbolBrush": series.color,
        "symbolPen": None,  # no marker outline
        "symbolSize": max(series.width * 3, 6),
    }
