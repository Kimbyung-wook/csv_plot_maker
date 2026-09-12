from csv_plot_maker.models.data_source import (
    SOURCE_COLOR_PALETTE,
    DataSource,
    SourceRef,
    UNASSIGNED_SOURCE_ID,
    color_for_index,
)


def test_color_for_index_cycles_through_the_palette():
    n = len(SOURCE_COLOR_PALETTE)
    assert color_for_index(0) == SOURCE_COLOR_PALETTE[0]
    assert color_for_index(n) == SOURCE_COLOR_PALETTE[0]
    assert color_for_index(n + 1) == SOURCE_COLOR_PALETTE[1]


def test_data_source_default_color_matches_color_for_index_zero():
    source = DataSource(id="a", path="a.csv", label="a")
    assert source.color == color_for_index(0)


def test_series_unassigned_source_id_sentinel_is_empty_string():
    # ProjectState.reconcile_data_sources remaps this exact value for
    # pre-multi-CSV-era layouts -- Series.source_id's own default must stay
    # in lockstep with it.
    from csv_plot_maker.models.series import Series

    assert Series(y_column="a").source_id == UNASSIGNED_SOURCE_ID == ""


def test_source_ref_from_source_copies_identity_fields_only():
    source = DataSource(id="a", path="a.csv", label="Alpha", color="#123456")

    ref = SourceRef.from_source(source)

    assert ref == SourceRef(id="a", path="a.csv", label="Alpha", color="#123456")
