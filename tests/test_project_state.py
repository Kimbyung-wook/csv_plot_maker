from csv_plot_maker.models.project import ProjectState


def test_build_default_grid_creates_expected_subplots():
    proj = ProjectState(grid_rows=2, grid_cols=2)
    proj.build_default_grid()

    assert len(proj.subplots) == 4
    positions = {(sp.row, sp.col) for sp in proj.subplots}
    assert positions == {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert proj.active_subplot_id == proj.subplots[0].id


def test_resize_grid_preserves_existing_subplots_by_position():
    proj = ProjectState(grid_rows=1, grid_cols=2)
    proj.build_default_grid()
    first_id = proj.subplots[0].id

    proj.resize_grid(2, 2)

    assert len(proj.subplots) == 4
    sp00 = next(sp for sp in proj.subplots if (sp.row, sp.col) == (0, 0))
    assert sp00.id == first_id


def test_resize_grid_shrink_drops_out_of_bounds_subplots_and_resets_active():
    proj = ProjectState(grid_rows=2, grid_cols=2)
    proj.build_default_grid()
    sp11 = next(sp for sp in proj.subplots if (sp.row, sp.col) == (1, 1))
    proj.active_subplot_id = sp11.id

    proj.resize_grid(1, 1)

    assert len(proj.subplots) == 1
    assert (proj.subplots[0].row, proj.subplots[0].col) == (0, 0)
    # the active subplot pointed at a position that no longer exists, so it must reset
    assert proj.active_subplot_id == proj.subplots[0].id
