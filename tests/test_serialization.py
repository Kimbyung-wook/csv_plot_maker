import json

from csv_plot_maker.models.project import ProjectState
from csv_plot_maker.models.serialization import load_project, save_project


def test_save_then_load_round_trips_legend_font_size(tmp_path):
    path = tmp_path / "layout.json"
    project = ProjectState(grid_rows=1, grid_cols=1)
    project.build_default_grid()
    project.legend_font_size = 11

    save_project(project, str(path))
    loaded = load_project(str(path))

    assert loaded.legend_font_size == 11


def test_load_project_defaults_legend_font_size_for_older_layout_files(tmp_path):
    # A layout saved before legend_font_size existed has no such key at all --
    # loading it must fall back to the same default as a brand-new project,
    # not raise or silently pick something else.
    path = tmp_path / "layout.json"
    project = ProjectState(grid_rows=1, grid_cols=1)
    project.build_default_grid()
    save_project(project, str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["legend_font_size"]
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_project(str(path))

    assert loaded.legend_font_size == 9


def test_save_then_load_round_trips_subplot_y_ranges(tmp_path):
    path = tmp_path / "layout.json"
    project = ProjectState(grid_rows=1, grid_cols=1)
    project.build_default_grid()
    project.subplots[0].y_range_left = [-1.0, 1.0]
    project.subplots[0].y_range_right = [-100.0, 100.0]

    save_project(project, str(path))
    loaded = load_project(str(path))

    assert loaded.subplots[0].y_range_left == [-1.0, 1.0]
    assert loaded.subplots[0].y_range_right == [-100.0, 100.0]


def test_load_project_defaults_y_ranges_to_none_for_older_layout_files(tmp_path):
    # Same backward-compat concern as legend_font_size above, but for a
    # per-subplot field instead of a top-level one.
    path = tmp_path / "layout.json"
    project = ProjectState(grid_rows=1, grid_cols=1)
    project.build_default_grid()
    save_project(project, str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["subplots"][0]["y_range_left"]
    del data["subplots"][0]["y_range_right"]
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_project(str(path))

    assert loaded.subplots[0].y_range_left is None
    assert loaded.subplots[0].y_range_right is None
