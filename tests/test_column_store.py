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


def test_is_sparse_true_when_mostly_nan():
    store = ColumnStore()
    store.columns["sparse"] = np.array([np.nan, np.nan, np.nan, 1.0])
    assert store.is_sparse("sparse") is True


def test_is_sparse_false_when_mostly_populated():
    store = ColumnStore()
    store.columns["dense"] = np.array([1.0, 2.0, np.nan, 4.0])
    assert store.is_sparse("dense") is False


def test_is_sparse_false_for_integer_columns():
    # Integer arrays can't hold NaN at all, so there's no missing-data signal
    # to key sparsity off of.
    store = ColumnStore()
    store.columns["ints"] = np.array([1, 2, 3], dtype=np.int32)
    assert store.is_sparse("ints") is False
