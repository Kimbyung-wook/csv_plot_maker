from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QWidget


def start_column_drag(
    widget: QWidget,
    pairs: list[tuple[str, str]],
    move: bool = False,
    series_ids: list[str] | None = None,
) -> None:
    """Shared drag-start for both column-list widgets that can be dropped
    onto a subplot (DraggableColumnList in the Data tab, SeriesListWidget in
    the series list): encodes `pairs` of (source_id, column_name) as plain
    text, one "move_flag\\tsource_id\\tcolumn_name\\tseries_id" line per
    pair.

    `move_flag` ("1"/"0") records *intent*: "1" means "this column is
    already plotted somewhere and relocating it is the point"
    (SeriesListWidget, dragging an already-placed series to another subplot
    cell), "0" means "add this column" (DraggableColumnList, dragging a raw
    column out of the Data tab) even if that same column happens to already
    be plotted elsewhere -- the Data tab is for adding series, not
    relocating them, so a column already in another subplot must still end
    up duplicated, not moved, when dragged from there.

    This flag rides in the plain-text payload itself rather than a separate
    custom MIME format: a custom format was not found to reliably survive a
    real mouse-driven (OS-level) drag on Windows, silently reading back
    empty on the drop side regardless of the actual drag source. Plain text
    is what source_id/column_name already use and that has always arrived
    intact, so the flag rides along with them instead.

    `series_ids`, when given (SeriesListWidget only, one id per pair, ""
    where unknown), names the *exact* already-placed Series being
    relocated. Without it, the drop handler can only match by
    (source_id, column_name), which is ambiguous -- and therefore refuses
    to move at all -- once that same column is already plotted in more
    than one other subplot. The series list always knows which specific
    series it's dragging, so it always supplies this.
    """
    if not pairs:
        return
    ids = series_ids if series_ids is not None else [""] * len(pairs)
    mime = QMimeData()
    move_flag = "1" if move else "0"
    mime.setText(
        "\n".join(
            f"{move_flag}\t{source_id}\t{column_name}\t{series_id}"
            for (source_id, column_name), series_id in zip(pairs, ids)
        )
    )
    drag = QDrag(widget)
    drag.setMimeData(mime)
    drag.exec(Qt.DropAction.CopyAction)
