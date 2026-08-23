"""Single source of truth for the version/build-date shown in the window title.

Keep __version__ in sync with pyproject.toml's [project].version, and bump
BUILD_DATE whenever a new standalone executable is built (see scripts in the
project root / DESIGN.md appendix A for the PyInstaller build command).
"""

__version__ = "0.1.0"
BUILD_DATE = "2026-08-23"
