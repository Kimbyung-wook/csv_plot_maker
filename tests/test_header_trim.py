from csv_plot_maker.data.header_trim import trim_headers


def test_trim_headers_removes_keyword_substrings():
    names = ["AVS_TC_AILDA::MODE_Value", "AVS_TC_AILDA::SPEED_Value"]
    result = trim_headers(names, ["AVS_TC_AILDA::", "_Value"])
    assert result == ["MODE", "SPEED"]


def test_trim_headers_with_no_keywords_is_a_no_op():
    names = ["a", "b"]
    assert trim_headers(names, []) == names


def test_trim_headers_deduplicates_collisions():
    names = ["FOO_a_BAR", "FOO_a_BAZ"]
    # both trim down to "a" once "_BAR"/"_BAZ" and "FOO_" are stripped away --
    # the trimming keyword list can't tell them apart, so the collision must
    # be disambiguated rather than one silently overwriting the other.
    result = trim_headers(names, ["FOO_", "_BAR", "_BAZ"])
    assert result == ["a", "a_1"]


def test_trim_headers_avoids_colliding_with_reserved_names():
    # trimming a real column down to exactly "Sequential" must not clobber
    # the synthetic Sequential column load_csv() always adds.
    result = trim_headers(["PREFIX_Sequential"], ["PREFIX_"])
    assert result == ["Sequential_1"]


def test_trim_headers_falls_back_to_original_when_fully_stripped():
    # A keyword that happens to match an entire header name would otherwise
    # leave a blank, unusable column name.
    result = trim_headers(["DEBUG"], ["DEBUG"])
    assert result == ["DEBUG"]


def test_trim_headers_skips_a_bumped_suffix_that_collides_with_another_name():
    # Two columns trim down to "RESERVED" (so the second one wants to become
    # "RESERVED_1", then a third "RESERVED_2"), but the third original column
    # already trims to exactly "RESERVED_2" on its own -- the counter must
    # skip past that collision instead of producing two "RESERVED_2" columns.
    names = ["RESERVED", "RESERVED", "RESERVED_2", "RESERVED"]
    result = trim_headers(names, [])
    assert result == ["RESERVED", "RESERVED_1", "RESERVED_2", "RESERVED_3"]
    assert len(result) == len(set(result))
