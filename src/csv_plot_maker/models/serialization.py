from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from csv_plot_maker.models.data_source import SourceRef
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
    # Pre-multi-CSV layouts stored one project-wide "link every subplot's X
    # axis" switch instead of today's per-subplot link_x_axis -- a layout
    # saved with that switch on should still open with every subplot linked,
    # since that's the exact panning behavior it was saved with.
    legacy_link_all = data.get("link_x_axes", False)
    subplots = []
    for sp in data["subplots"]:
        sp = dict(sp)
        if legacy_link_all and "link_x_axis" not in sp:
            sp["link_x_axis"] = True
        # Pre-per-series-X layouts stored one X column/source/offset per
        # subplot, applied uniformly to every series in it -- migrate that
        # onto each series individually now that X is a series-level
        # property (see Series.x_column), since that's the exact X data
        # every one of those series was actually plotted against.
        # x_source_id is dropped outright: a series' X now always comes from
        # its own source_id, which every series already carries.
        legacy_x_column = sp.pop("x_column", None)
        legacy_x_offset = sp.pop("x_offset", 0.0)
        sp.pop("x_source_id", None)
        series_list = []
        for s in sp["series"]:
            s = dict(s)
            if legacy_x_column and "x_column" not in s:
                s["x_column"] = legacy_x_column
                s["x_offset"] = legacy_x_offset
            series_list.append(Series(**s))
        sp["series"] = series_list
        subplots.append(SubplotConfig(**sp))
    data_sources = [SourceRef(**ds) for ds in data.get("data_sources", [])]
    return ProjectState(
        grid_rows=data["grid_rows"],
        grid_cols=data["grid_cols"],
        active_subplot_id=data.get("active_subplot_id"),
        subplots=subplots,
        legend_font_size=data.get("legend_font_size", 9),
        data_sources=data_sources,
    )
