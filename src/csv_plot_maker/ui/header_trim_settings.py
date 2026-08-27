from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_FILENAME = "header_trim_keywords.json"


def app_dir() -> Path:
    """Directory the default keyword list file lives next to.

    A PyInstaller-frozen build's `sys.executable` is the .exe itself, so a
    "header_trim_keywords.json" placed there travels with the app and is
    easy to hand-edit or share between machines. Running from source has no
    such fixed executable, so this falls back to the working directory
    (which for normal `uv run` usage is the repo root).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def default_keywords_path() -> Path:
    return app_dir() / DEFAULT_FILENAME


def load_keywords_from_file(path: Path | str) -> list[str]:
    """Read a keyword list from an arbitrary JSON file. Raises on failure --
    callers driven by explicit user action (the dialog's "Load..." button)
    should surface that to the user rather than silently swallowing it."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of keyword strings")
    return [str(item) for item in data]


def save_keywords_to_file(path: Path | str, keywords: list[str]) -> None:
    Path(path).write_text(json.dumps(keywords, indent=2), encoding="utf-8")


def load_default_keywords() -> list[str]:
    """Read the default keyword file next to the app, if one exists.

    Pure read: never creates or writes anything, so simply starting the app
    (or opening the Header Trimming dialog) can't conjure a file that wasn't
    already placed there on purpose. Missing file or unparsable content both
    just mean "no default configured yet" -- fail open to an empty list.
    """
    path = default_keywords_path()
    if not path.exists():
        return []
    try:
        return load_keywords_from_file(path)
    except (OSError, ValueError):
        return []
