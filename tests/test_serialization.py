import json

from csv_plot_maker.models.data_source import SourceRef
from csv_plot_maker.models.project import ProjectState
from csv_plot_maker.models.serialization import load_project, save_project
from csv_plot_maker.models.series import Series


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


def test_save_then_load_round_trips_series_scale_and_offset(tmp_path):
    path = tmp_path / "layout.json"
    project = ProjectState(grid_rows=1, grid_cols=1)
    project.build_default_grid()
    project.subplots[0].add_series(Series(y_column="altitude_m", scale=2.5, offset=-3.0))

    save_project(project, str(path))
    loaded = load_project(str(path))

    loaded_series = loaded.subplots[0].series[0]
    assert loaded_series.scale == 2.5
    assert loaded_series.offset == -3.0


def test_load_project_defaults_scale_and_offset_for_older_layout_files(tmp_path):
    # Same backward-compat concern as legend_font_size above, but for a
    # per-series field pair introduced after scale/offset didn't exist yet.
    path = tmp_path / "layout.json"
    project = ProjectState(grid_rows=1, grid_cols=1)
    project.build_default_grid()
    project.subplots[0].add_series(Series(y_column="altitude_m"))

    save_project(project, str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["subplots"][0]["series"][0]["scale"]
    del data["subplots"][0]["series"][0]["offset"]
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_project(str(path))

    loaded_series = loaded.subplots[0].series[0]
    assert loaded_series.scale == 1.0
    assert loaded_series.offset == 0.0


def test_save_then_load_round_trips_data_sources_and_per_series_source_id(tmp_path):
    path = tmp_path / "layout.json"
    project = ProjectState(grid_rows=1, grid_cols=1)
    project.build_default_grid()
    project.data_sources = [
        SourceRef(id="src1", path="flight_a.csv", label="flight_a", color="#dbeafe"),
        SourceRef(id="src2", path="flight_b.csv", label="flight_b", color="#dcfce7"),
    ]
    project.subplots[0].add_series(Series(y_column="alt", source_id="src1", x_column="timestamp"))
    project.subplots[0].add_series(Series(y_column="spd", source_id="src2", x_column="timestamp"))

    save_project(project, str(path))
    loaded = load_project(str(path))

    assert loaded.data_sources == [
        SourceRef(id="src1", path="flight_a.csv", label="flight_a", color="#dbeafe"),
        SourceRef(id="src2", path="flight_b.csv", label="flight_b", color="#dcfce7"),
    ]
    assert [s.source_id for s in loaded.subplots[0].series] == ["src1", "src2"]


def test_load_project_defaults_data_sources_and_source_id_for_older_layout_files(tmp_path):
    # A pre-multi-CSV layout has no "data_sources" key and no per-series
    # source_id at all -- loading it must not raise, and every reference
    # should fall back to the empty-string default (MainWindow then resolves
    # that to whichever single CSV is currently open).
    path = tmp_path / "layout.json"
    project = ProjectState(grid_rows=1, grid_cols=1)
    project.build_default_grid()
    project.subplots[0].add_series(Series(y_column="altitude_m"))
    save_project(project, str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["data_sources"]
    del data["subplots"][0]["series"][0]["source_id"]
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_project(str(path))

    assert loaded.data_sources == []
    assert loaded.subplots[0].series[0].source_id == ""


def test_load_project_migrates_a_pre_per_series_x_layout_onto_every_series(tmp_path):
    # A layout saved before X became a per-series property (see
    # Series.x_column) stored one X column/source/offset per subplot,
    # applied uniformly to every series in it -- loading it must copy that
    # onto each series individually, since that's the exact X data each one
    # was actually plotted against.
    path = tmp_path / "layout.json"
    project = ProjectState(grid_rows=1, grid_cols=1)
    project.build_default_grid()
    project.subplots[0].add_series(Series(y_column="alt", source_id="src1"))
    project.subplots[0].add_series(Series(y_column="spd", source_id="src1"))
    save_project(project, str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    for series in data["subplots"][0]["series"]:
        del series["x_column"]
        del series["x_offset"]
    data["subplots"][0]["x_column"] = "timestamp"
    data["subplots"][0]["x_source_id"] = "src1"
    data["subplots"][0]["x_offset"] = 5.0
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_project(str(path))

    assert [s.x_column for s in loaded.subplots[0].series] == ["timestamp", "timestamp"]
    assert [s.x_offset for s in loaded.subplots[0].series] == [5.0, 5.0]


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
