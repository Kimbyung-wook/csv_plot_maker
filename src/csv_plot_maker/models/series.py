from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

LineStyle = Literal["solid", "dash", "dot", "dashdot"]
Axis = Literal["primary", "secondary"]


@dataclass
class Series:
    """One plotted line: a Y column with an axis assignment and visual style.

    Identified by `id`, not by column name, so the same column can be added
    as multiple independent series (duplicate selection requirement).
    """

    y_column: str
    axis: Axis = "primary"
    color: str = "#1f77b4"
    line_style: LineStyle = "solid"
    marker: str | None = None
    width: float = 1.5
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
