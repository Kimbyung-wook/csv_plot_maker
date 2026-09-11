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
        except BaseException as exc:
            # Must be BaseException, not Exception: some native extensions
            # (polars/pyo3 in particular) surface an internal Rust panic as
            # pyo3_runtime.PanicException, which subclasses BaseException
            # directly so it can't be mistaken for an ordinary catchable
            # error -- but that also means a bare `except Exception` here
            # lets it escape uncaught. When that happens neither `finished`
            # nor `error` ever fires, so whatever's waiting on this worker
            # (e.g. a modal "Loading..." progress dialog with no cancel
            # button) is left showing forever with no way to close it.
            self.signals.error.emit(str(exc))
        else:
            self.signals.finished.emit(result)
