from csv_plot_maker.models.series import Series
from csv_plot_maker.plotting.style_map import MARKER_CHOICES, symbol_kwargs


def test_marker_choices_has_a_distinct_dot_entry():
    assert "Dot" in MARKER_CHOICES
    assert MARKER_CHOICES["Dot"] == "dot"
    # Every label must round-trip to a unique marker value, or the Style
    # panel's label-from-value lookup (`next(k for k, v in ... if v == x)`)
    # would ambiguously resolve to whichever label happens to come first.
    assert len(set(MARKER_CHOICES.values())) == len(MARKER_CHOICES)


def test_dot_marker_uses_a_small_fixed_size_regardless_of_width():
    series = Series(y_column="a", marker="dot", width=10.0)
    kwargs = symbol_kwargs(series)
    assert kwargs["symbol"] == "o"
    assert kwargs["symbolSize"] < 10.0 * 3


def test_circle_marker_still_scales_with_width():
    series = Series(y_column="a", marker="o", width=10.0)
    kwargs = symbol_kwargs(series)
    assert kwargs["symbol"] == "o"
    assert kwargs["symbolSize"] == 30.0


def test_no_marker_hides_symbol():
    series = Series(y_column="a", marker=None)
    kwargs = symbol_kwargs(series)
    assert kwargs["symbol"] is None
    assert kwargs["symbolSize"] == 0
