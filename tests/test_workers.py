from csv_plot_maker.utils.workers import CallableWorker


class _NativePanic(BaseException):
    """Stand-in for pyo3_runtime.PanicException, which (like this class)
    subclasses BaseException directly rather than Exception, specifically so
    a native Rust panic surfaced through pyo3 can't be mistaken for an
    ordinary catchable error."""


def test_run_emits_finished_on_success():
    results = []
    worker = CallableWorker(lambda: 42)
    worker.signals.finished.connect(results.append)
    worker.run()
    assert results == [42]


def test_run_emits_error_for_ordinary_exception():
    messages = []
    worker = CallableWorker(lambda: (_ for _ in ()).throw(ValueError("boom")))
    worker.signals.error.connect(messages.append)
    worker.run()
    assert messages == ["boom"]


def test_run_emits_error_instead_of_hanging_on_a_baseexception_that_is_not_an_exception():
    # A worker with nothing else watching it (e.g. a caller's modal progress
    # dialog with no cancel button) must never let anything escape run()
    # uncaught -- an exception type that skips a plain `except Exception`
    # would otherwise leave that caller waiting forever with no error and no
    # way to close it. See CallableWorker.run()'s comment.
    messages = []
    worker = CallableWorker(lambda: (_ for _ in ()).throw(_NativePanic("native panic")))
    worker.signals.error.connect(messages.append)
    worker.run()
    assert messages == ["native panic"]
