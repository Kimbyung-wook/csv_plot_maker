from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest

from csv_plot_maker.data.loader import load_csv, peek_schema

FIXTURE = Path(__file__).parent / "fixtures" / "small.csv"


def test_peek_schema_returns_column_names():
    names = peek_schema(str(FIXTURE))
    assert names == ["Sequential", "t", "a", "b", "label"]


def test_load_csv_returns_correct_row_count_and_values():
    store = load_csv(str(FIXTURE))
    assert store.row_count == 3
    assert store.get("a").tolist() == [1.0, 2.5, 3.0]
    assert store.get("Sequential").tolist() == [1.0, 2.0, 3.0]
    assert store.numeric["Sequential"] is True
    assert store.numeric["a"] is True
    assert store.numeric["label"] is False


def test_load_csv_never_materializes_non_numeric_columns():
    # "label" can never be plotted (see ColumnStore.numeric_column_names()),
    # so its array data should never be converted/stored at all -- only its
    # dtype/numeric flag.
    store = load_csv(str(FIXTURE))
    assert "label" not in store.columns
    assert "label" in store.dtypes
    assert store.numeric["label"] is False


def test_load_csv_does_not_retry_on_memory_error():
    # A MemoryError on the very first parse attempt must propagate
    # immediately instead of triggering the two progressively more
    # expensive full-file re-parse fallbacks -- retrying an already-OOM'd
    # load is pointless and only makes the situation worse.
    with patch("csv_plot_maker.data.loader.pl.read_csv", side_effect=MemoryError("boom")) as mock_read:
        with pytest.raises(MemoryError):
            load_csv(str(FIXTURE))
    assert mock_read.call_count == 1


def test_load_csv_still_retries_on_schema_error():
    # Genuine schema/parsing failures (pl.exceptions.PolarsError and its
    # subclasses) should still fall through the existing 3-step retry ladder.
    real_read_csv = pl.read_csv
    calls = []

    def flaky_read_csv(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) < 3:
            raise pl.exceptions.ComputeError("simulated schema failure")
        return real_read_csv(*args, **kwargs)

    with patch("csv_plot_maker.data.loader.pl.read_csv", side_effect=flaky_read_csv):
        store = load_csv(str(FIXTURE))

    assert len(calls) == 3
    assert store.row_count == 3
