import faulthandler
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from csv_plot_maker.ui.main_window import MainWindow


def _enable_crash_log() -> None:
    """On a native crash (e.g. an access violation inside Qt), write the Python
    stack of every thread to %LOCALAPPDATA%\\CSV Plot Maker\\crash.log -- a built
    windowed .exe has no console to print it to. The file is overwritten on
    each start, so it holds only the last run. Windows may also log exceptions
    there that were caught and handled, so only a "Fatal Python error" /
    stack at the very end of the file -- with the app actually gone -- means
    a crash."""
    try:
        log_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CSV Plot Maker"
        log_dir.mkdir(parents=True, exist_ok=True)
        # Kept open for the life of the process: faulthandler writes to it from
        # its signal handler, where opening a file is no longer possible.
        log_file = open(log_dir / "crash.log", "w", encoding="utf-8")  # noqa: SIM115
        faulthandler.enable(file=log_file, all_threads=True)
    except OSError:
        pass  # diagnostics only -- never stop the app from starting


def main() -> None:
    _enable_crash_log()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1400, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
