import numpy as np

from csv_plot_maker.data.column_store import ColumnStore


def test_column_store_basic():
    store = ColumnStore()
    assert store.is_empty()

    store.columns["x"] = np.array([1, 2, 3])
    store.numeric["x"] = True

    assert not store.is_empty()
    assert store.column_names() == ["x"]
    assert store.numeric_column_names() == ["x"]
