from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from csv_plot_maker.models.project import ProjectState
from csv_plot_maker.models.series import Series
from csv_plot_maker.models.subplot import SubplotConfig


def config_path_for_csv(csv_path: str) -> Path:
    """The layout config for a CSV lives alongside it, same basename, .json."""
    return Path(csv_path).with_suffix(".json")


def save_project(project: ProjectState, path: str) -> None:
    # csv_path is deliberately left out: it's runtime-only state (which CSV
    # is currently open, used to pick Save Layout's default path), not part
    # of the layout itself -- keeping it in the file would misleadingly
    # suggest that loading this layout also reopens that CSV, which it never
    # has (every load path immediately overwrites it with whatever CSV is
    # actually open). Leaving it out also keeps the JSON genuinely portable
    # across different CSVs.
    data = asdict(project)
    del data["csv_path"]
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_project(path: str) -> ProjectState:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    subplots = [
        SubplotConfig(**{**sp, "series": [Series(**s) for s in sp["series"]]})
        for sp in data["subplots"]
    ]
    return ProjectState(
        grid_rows=data["grid_rows"],
        grid_cols=data["grid_cols"],
        active_subplot_id=data.get("active_subplot_id"),
        subplots=subplots,
        link_x_axes=data.get("link_x_axes", False),
    )
