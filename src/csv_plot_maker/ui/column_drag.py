from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QWidget


def start_column_drag(widget: QWidget, pairs: list[tuple[str, str]]) -> None:
    """Shared drag-start for both column-list widgets that can be dropped
    onto a subplot (DraggableColumnList in the Data tab, SeriesListWidget in
    the series list): encodes `pairs` of (source_id, column_name) as plain
    text, one "source_id\\tcolumn_name" pair per line -- the drop target
    (PlotGridWidget.dropEvent) needs to know which file each column came
    from, since the same column name can exist in more than one open file,
    and handles a drop from either source identically as a result.
    """
    if not pairs:
        return
    mime = QMimeData()
    mime.setText("\n".join(f"{source_id}\t{column_name}" for source_id, column_name in pairs))
    drag = QDrag(widget)
    drag.setMimeData(mime)
    drag.exec(Qt.DropAction.CopyAction)
