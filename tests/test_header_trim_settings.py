import sys

import pytest

from csv_plot_maker.ui import header_trim_settings as hts


def test_app_dir_uses_executable_folder_when_frozen(tmp_path, monkeypatch):
    fake_exe = tmp_path / "dist" / "csv-plot-maker.exe"
    fake_exe.parent.mkdir(parents=True)
    fake_exe.touch()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    assert hts.app_dir() == fake_exe.parent


def test_app_dir_uses_cwd_when_not_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.chdir(tmp_path)

    assert hts.app_dir() == tmp_path


def test_save_then_load_keywords_from_file_round_trips(tmp_path):
    path = tmp_path / "keywords.json"

    hts.save_keywords_to_file(path, ["foo", "bar"])

    assert hts.load_keywords_from_file(path) == ["foo", "bar"]


def test_load_keywords_from_file_rejects_non_list_json(tmp_path):
    path = tmp_path / "keywords.json"
    path.write_text('{"not": "a list"}', encoding="utf-8")

    with pytest.raises(ValueError):
        hts.load_keywords_from_file(path)


def test_load_keywords_from_file_raises_on_missing_file(tmp_path):
    with pytest.raises(OSError):
        hts.load_keywords_from_file(tmp_path / "does_not_exist.json")


def test_load_default_keywords_returns_empty_list_when_no_default_file(tmp_path, monkeypatch):
    monkeypatch.setattr(hts, "app_dir", lambda: tmp_path)

    assert hts.load_default_keywords() == []
    # a pure read must never create the file itself.
    assert not (tmp_path / hts.DEFAULT_FILENAME).exists()


def test_load_default_keywords_reads_the_default_file_next_to_the_app(tmp_path, monkeypatch):
    monkeypatch.setattr(hts, "app_dir", lambda: tmp_path)
    (tmp_path / hts.DEFAULT_FILENAME).write_text('["foo", "bar"]', encoding="utf-8")

    assert hts.load_default_keywords() == ["foo", "bar"]


def test_load_default_keywords_returns_empty_list_on_corrupted_default_file(tmp_path, monkeypatch):
    monkeypatch.setattr(hts, "app_dir", lambda: tmp_path)
    (tmp_path / hts.DEFAULT_FILENAME).write_text("not valid json", encoding="utf-8")

    assert hts.load_default_keywords() == []
