from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from csv_plot_maker.models.data_source import SourceRef
from csv_plot_maker.models.project import ProjectState
from csv_plot_maker.models.series import Series
from csv_plot_maker.models.subplot import SubplotConfig

# Marks a layout file that holds several layout tabs (see save_workspace).
# A file without a "tabs" list is a single-tab layout -- the format every
# layout file had before tabs existed, still used by Save Tab As.
WORKSPACE_FORMAT = "csv_plot_maker.layout_tabs"
WORKSPACE_VERSION = 1


def config_path_for_csv(csv_path: str) -> Path:
    """The layout config for a CSV lives alongside it, same basename, .json."""
    return Path(csv_path).with_suffix(".json")


def default_tab_name(existing: list[str]) -> str:
    """"Layout N" with the smallest N >= 1 not already taken by another tab."""
    taken = set(existing)
    n = 1
    while f"Layout {n}" in taken:
        n += 1
    return f"Layout {n}"


def duplicate_tab_name(name: str, existing: list[str]) -> str:
    """"name (N)" with the smallest N >= 2 not already taken by another tab."""
    taken = set(existing)
    n = 2
    while f"{name} ({n})" in taken:
        n += 1
    return f"{name} ({n})"


def _project_to_dict(project: ProjectState) -> dict:
    # csv_path is deliberately left out: it's runtime-only state (which CSV
    # is currently open), not part of the layout itself -- keeping it in the
    # file would misleadingly suggest that loading this layout also reopens
    # that CSV, which it never does. Leaving it out also keeps the JSON
    # genuinely portable across different CSVs.
    data = asdict(project)
    del data["csv_path"]
    return data


def save_project(project: ProjectState, path: str) -> None:
    """Save one layout tab (the single-tab layout format). The tab's name is
    not stored: a single-tab layout is named after its file when loaded."""
    data = _project_to_dict(project)
    del data["name"]
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


@dataclass
class LayoutFile:
    """What a layout file holds: one or more layout tabs, in tab order."""

    tabs: list[ProjectState] = field(default_factory=list)
    active_tab: int = 0
    legend_font_size: int = 9
    # False for a single-tab layout file (including every file saved before
    # layout tabs existed).
    multi_tab: bool = False


def save_workspace(layout: LayoutFile, path: str) -> None:
    """Save every layout tab, with its name, into one file."""
    data = {
        "format": WORKSPACE_FORMAT,
        "version": WORKSPACE_VERSION,
        "active_tab": layout.active_tab,
        "legend_font_size": layout.legend_font_size,
        "tabs": [_project_to_dict(tab) for tab in layout.tabs],
    }
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_layout_file(path: str) -> LayoutFile:
    """Load either kind of layout file. A single-tab file becomes one tab
    named after the file; a multi-tab file keeps the tab names saved in it."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "tabs" not in data:
        project = _project_from_dict(data)
        project.name = Path(path).stem
        return LayoutFile(
            tabs=[project], active_tab=0, legend_font_size=project.legend_font_size, multi_tab=False
        )
    tabs = [_project_from_dict(tab) for tab in data["tabs"]]
    if not tabs:
        raise ValueError("the layout file has no tabs")
    names: list[str] = []
    for tab in tabs:
        if not tab.name:
            tab.name = default_tab_name(names)
        names.append(tab.name)
    legend_font_size = data.get("legend_font_size", 9)
    for tab in tabs:
        tab.legend_font_size = legend_font_size
    active_tab = data.get("active_tab", 0)
    if not 0 <= active_tab < len(tabs):
        active_tab = 0
    return LayoutFile(tabs=tabs, active_tab=active_tab, legend_font_size=legend_font_size, multi_tab=True)


def load_project(path: str) -> ProjectState:
    """Load a single-tab layout file (see load_layout_file for either kind)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return _project_from_dict(data)


def _project_from_dict(data: dict) -> ProjectState:
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
        name=data.get("name", ""),
        grid_rows=data["grid_rows"],
        grid_cols=data["grid_cols"],
        active_subplot_id=data.get("active_subplot_id"),
        subplots=subplots,
        legend_font_size=data.get("legend_font_size", 9),
        data_sources=data_sources,
    )
