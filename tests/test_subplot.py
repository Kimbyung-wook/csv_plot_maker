from csv_plot_maker.models.series import Series
from csv_plot_maker.models.subplot import SubplotConfig


def test_x_signature_none_when_empty():
    subplot = SubplotConfig(row=0, col=0)
    assert subplot.x_signature() is None


def test_x_signature_none_when_series_disagree():
    subplot = SubplotConfig(row=0, col=0)
    subplot.add_series(Series(y_column="a", source_id="s1", x_column="t"))
    subplot.add_series(Series(y_column="b", source_id="s2", x_column="t"))
    assert subplot.x_signature() is None


def test_x_signature_agrees_when_every_series_shares_source_column_and_offset():
    subplot = SubplotConfig(row=0, col=0)
    subplot.add_series(Series(y_column="a", source_id="s1", x_column="t", x_offset=1.0))
    subplot.add_series(Series(y_column="b", source_id="s1", x_column="t", x_offset=1.0))
    assert subplot.x_signature() == ("s1", "t", 1.0)


def test_x_signature_disagrees_on_differing_offset_alone():
    subplot = SubplotConfig(row=0, col=0)
    subplot.add_series(Series(y_column="a", source_id="s1", x_column="t", x_offset=0.0))
    subplot.add_series(Series(y_column="b", source_id="s1", x_column="t", x_offset=1.0))
    assert subplot.x_signature() is None


def test_default_x_label_blank_when_no_shared_signature():
    subplot = SubplotConfig(row=0, col=0)
    assert subplot.default_x_label() == ""


def test_default_x_label_is_the_shared_x_column():
    subplot = SubplotConfig(row=0, col=0)
    subplot.add_series(Series(y_column="a", source_id="s1", x_column="timestamp"))
    assert subplot.default_x_label() == "timestamp"
