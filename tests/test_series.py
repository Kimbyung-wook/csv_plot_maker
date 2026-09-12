import numpy as np

from csv_plot_maker.data.column_store import ColumnStore
from csv_plot_maker.models.data_source import DataSource
from csv_plot_maker.models.series import Series


def _source_with(**columns: np.ndarray) -> DataSource:
    store = ColumnStore(row_count=len(next(iter(columns.values()))))
    for name, arr in columns.items():
        store.set_column(name, arr, is_numeric=True)
    return DataSource(id="src", path="src.csv", label="src", store=store)


def test_is_ready_false_without_an_x_column_chosen():
    series = Series(y_column="a", x_column="")
    source = _source_with(a=np.array([1.0, 2.0]))
    assert series.is_ready(source) is False


def test_is_ready_false_when_source_is_none_or_unloaded():
    series = Series(y_column="a", x_column="t")
    assert series.is_ready(None) is False
    assert series.is_ready(DataSource(id="src", path="src.csv", label="src", store=None)) is False


def test_is_ready_true_once_x_column_set_and_source_loaded():
    series = Series(y_column="a", x_column="t")
    source = _source_with(t=np.array([0.0, 1.0]), a=np.array([1.0, 2.0]))
    assert series.is_ready(source) is True


def test_x_data_applies_offset():
    series = Series(y_column="a", x_column="t", x_offset=5.0)
    source = _source_with(t=np.array([0.0, 1.0]), a=np.array([1.0, 2.0]))
    assert list(series.x_data(source)) == [5.0, 6.0]


def test_y_data_applies_scale_then_offset():
    series = Series(y_column="a", x_column="t", scale=2.0, offset=1.0)
    source = _source_with(t=np.array([0.0, 1.0]), a=np.array([1.0, 2.0]))
    assert list(series.y_data(source)) == [3.0, 5.0]
