"""Hand removed graphics items to Qt's deferred deletion instead of letting
Python free them on the spot.

Without this, a QGraphicsItem that was just removed from the scene (a curve
of a closed CSV, a subplot of a rebuilt grid, ...) is destroyed the moment its
last Python reference goes away -- i.e. synchronously, from inside whatever
Qt/pyqtgraph call happened to drop that reference, possibly while Qt is still
in the middle of processing the scene. Crash dumps of the app closing one CSV
and opening another showed exactly that: shiboken's wrapper dealloc deleting
a C++ graphics item, followed by an access violation inside QGraphicsScene's
item bookkeeping (Qt6Widgets.dll).

defer_delete() instead keeps the items referenced, asks Qt to delete the
QObject-based ones via deleteLater() -- run by the event loop once control is
back at the top level, the documented safe point -- and only drops the Python
references a while later, by which time the C++ objects are already gone (so
dropping them deletes nothing).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QGraphicsItem

# Long enough for the DeferredDelete events posted alongside to have been
# processed first; the exact value doesn't matter beyond that.
_RELEASE_DELAY_MS = 2000

_parked: list[list[object]] = []


def defer_delete(*items: object) -> None:
    batch: list[object] = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, QGraphicsItem) and item.scene() is not None:
            item.scene().removeItem(item)
        if isinstance(item, QObject):
            try:
                item.deleteLater()
            except RuntimeError:  # C++ side already gone
                continue
        batch.append(item)
    if not batch:
        return
    _parked.append(batch)
    QTimer.singleShot(_RELEASE_DELAY_MS, _release_oldest)


def _release_oldest() -> None:
    if _parked:
        _parked.pop(0)
