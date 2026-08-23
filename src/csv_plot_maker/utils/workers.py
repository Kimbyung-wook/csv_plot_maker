from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


class CallableWorker(QRunnable):
    """Runs a zero-arg callable on a QThreadPool thread and emits its result on the main thread."""

    def __init__(self, fn: Callable[[], object]) -> None:
        super().__init__()
        self._fn = fn
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # surfaced to the UI via the error signal
            self.signals.error.emit(str(exc))
        else:
            self.signals.finished.emit(result)
