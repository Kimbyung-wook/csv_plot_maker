from pathlib import Path
from unittest.mock import patch

import numpy as np
import polars as pl
import pytest

from csv_plot_maker.data.loader import load_csv, peek_schema

FIXTURE = Path(__file__).parent / "fixtures" / "small.csv"
PRECISION_FIXTURE = Path(__file__).parent / "fixtures" / "precision.csv"
INTEGERS_FIXTURE = Path(__file__).parent / "fixtures" / "integers.csv"
RAGGED_FIXTURE = Path(__file__).parent / "fixtures" / "ragged.csv"
TIME_STRING_FIXTURE = Path(__file__).parent / "fixtures" / "time_string.csv"
SPARSE_NUMERIC_FIXTURE = Path(__file__).parent / "fixtures" / "sparse_numeric.csv"
HUGE_INTEGERS_FIXTURE = Path(__file__).parent / "fixtures" / "huge_integers.csv"


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


def test_load_csv_downcasts_small_magnitude_float_columns_to_float32():
    # "coarse" only has simple binary-fraction values (1.5, 2.25, 3.75), so
    # halving its footprint to float32 should be lossless -- see
    # _downcast_to_float32_if_safe().
    store = load_csv(str(PRECISION_FIXTURE))
    assert store.get("coarse").dtype == np.float32
    assert store.get("coarse").tolist() == [1.5, 2.25, 3.75]


def test_load_csv_keeps_large_magnitude_float_columns_as_float64():
    # "precise" holds values above 2**24 -- float32 can no longer represent
    # every integer exactly at that magnitude, so this column must stay
    # float64 regardless of the round-trip tolerance check.
    store = load_csv(str(PRECISION_FIXTURE))
    assert store.get("precise").dtype == np.float64


def test_load_csv_narrows_small_integer_columns():
    # polars infers whole-number CSV columns as Int64 regardless of their
    # actual range -- "small" only ever holds 1..3, so it should be narrowed
    # to the smallest dtype that fits (int8), not left at 8 bytes/value.
    store = load_csv(str(INTEGERS_FIXTURE))
    assert store.get("small").dtype == np.int8
    assert store.get("small").tolist() == [1, 2, 3]


def test_load_csv_keeps_wide_integer_columns_at_the_width_they_need():
    # "big" holds values above int32's range, so it must stay/become int64
    # rather than being narrowed into something that would overflow.
    store = load_csv(str(INTEGERS_FIXTURE))
    assert store.get("big").dtype == np.int64
    assert store.get("big").tolist() == [5000000000, 5000000001, 5000000002]


def test_load_csv_handles_nullable_integer_columns_via_float32_path():
    # A CSV integer column with a blank cell comes back from polars'
    # to_numpy() as float64 with NaN for the null (not an int dtype at all),
    # so it must go through the float32-downcast safety check, not the
    # integer-narrowing one.
    store = load_csv(str(INTEGERS_FIXTURE))
    arr = store.get("nullable")
    assert arr.dtype == np.float32
    assert arr[0] == 1.0
    assert np.isnan(arr[1])
    assert arr[2] == 3.0


def test_load_csv_keeps_entirely_empty_trailing_column_as_all_nan_numeric():
    # "b" is never written on any row (ragged CSV: rows just stop after "a"
    # instead of writing a trailing empty field) -- polars can't infer a
    # dtype for an all-null column and falls back to String, but this must
    # still be treated as an empty *numeric* column (all-NaN), not dropped
    # like a genuine text column.
    store = load_csv(str(RAGGED_FIXTURE))
    assert store.numeric["b"] is True
    arr = store.get("b")
    assert arr.dtype == np.float64
    assert arr.shape == (3,)
    assert np.all(np.isnan(arr))


def test_load_csv_converts_time_strings_to_seconds():
    # "t" holds HH:MM:SS.fff strings -- try_parse_dates infers pl.Time, and
    # load_csv should convert its physical (nanoseconds-since-midnight)
    # representation down to seconds, the unit users plot against.
    store = load_csv(str(TIME_STRING_FIXTURE))
    assert store.numeric["t"] is True
    arr = store.get("t")
    assert arr.dtype == np.float64
    assert np.allclose(arr, [5025.678, 5026.678, 5027.678])


def test_load_csv_recovers_int_columns_that_polars_misjudged_as_string():
    # "sparse_int" is null for its first 120 rows (past polars' sampled
    # schema-inference window) and only holds real integers ("1", "2") much
    # later -- polars can't guess a numeric dtype from an all-null sample and
    # defaults to String, then parses the real values as their string form
    # without ever raising the schema error the load_csv() retry ladder
    # watches for. The strict-cast salvage must recover this as numeric
    # instead of leaving it dropped as text. It's mostly null (same as any
    # nullable Int64 column), so it comes back through the float32 path, not
    # a true integer dtype -- see the nullable-integer test for integers.csv.
    store = load_csv(str(SPARSE_NUMERIC_FIXTURE))
    assert store.numeric["sparse_int"] is True
    arr = store.get("sparse_int")
    assert arr.dtype == np.float32
    assert arr[120] == 1
    assert arr[135] == 2
    assert np.isnan(arr[0])


def test_load_csv_recovers_float_columns_that_polars_misjudged_as_string():
    # Same scenario as the int case above, but the salvaged values have a
    # decimal point -- the Int64 cast attempt must fail and fall through to
    # the Float64 cast rather than being dropped entirely.
    store = load_csv(str(SPARSE_NUMERIC_FIXTURE))
    assert store.numeric["sparse_float"] is True
    arr = store.get("sparse_float")
    assert arr.dtype in (np.float32, np.float64)
    assert arr[120] == pytest.approx(1.5)
    assert arr[135] == pytest.approx(2.75)


def test_load_csv_still_drops_genuine_text_columns_misjudged_as_string():
    # "label" holds real, non-numeric text ("x"/"y") -- the strict-cast
    # salvage must fail for it (as intended) and it must still be dropped
    # like any other non-plottable text column, not silently coerced.
    store = load_csv(str(SPARSE_NUMERIC_FIXTURE))
    assert store.numeric["label"] is False
    assert "label" not in store.columns


def test_peek_schema_applies_header_trim_keywords():
    names = peek_schema(str(FIXTURE), header_trim_keywords=["lab"])
    assert names == ["Sequential", "t", "a", "b", "el"]


def test_load_csv_applies_header_trim_keywords_to_stored_column_names():
    store = load_csv(str(FIXTURE), header_trim_keywords=["lab"])
    assert "label" not in store.dtypes
    assert "el" in store.dtypes
    assert store.numeric["el"] is False


def test_load_csv_does_not_retry_on_memory_error():
    # A MemoryError on the very first parse attempt must propagate
    # immediately instead of triggering the two progressively more
    # expensive full-file re-parse fallbacks -- retrying an already-OOM'd
    # load is pointless and only makes the situation worse.
    with patch("csv_plot_maker.data.loader.pl.read_csv", side_effect=MemoryError("boom")) as mock_read:
        with pytest.raises(MemoryError):
            load_csv(str(FIXTURE))
    assert mock_read.call_count == 1


def test_load_csv_handles_columns_beyond_int64_range():
    # A value beyond Int64's range (e.g. a raw counter overflowing into the
    # UInt64 range) makes polars infer Int128 for the whole column -- and
    # polars' numpy interop has no conversion for that dtype: Series.to_numpy()
    # panics natively (pyo3_runtime.PanicException, not a catchable Python
    # exception) rather than raising. Before this was special-cased, that
    # panic escaped load_csv() entirely, and since it isn't an Exception
    # subclass, CallableWorker's try/except never saw it either -- so a real
    # multi-CSV session loading a file with a column like this got a "Loading
    # ..." progress dialog that never closed (see CallableWorker.run() and its
    # comment for the other half of this fix).
    store = load_csv(str(HUGE_INTEGERS_FIXTURE))
    assert store.numeric["huge"] is True
    arr = store.get("huge")
    assert arr.dtype == np.float64
    assert arr.tolist() == [0.0, 18446744073709551614.0]


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
