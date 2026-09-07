"""Magento refuses a script whose integrity hash does not match, silently."""

import json

import pytest

from manipulus import integrity


def make_store(tmp_path, recorded_hash: str | None = None):
    static = tmp_path / "pub" / "static"
    area = static / "frontend"
    theme = area / "Magento" / "luma" / "en_US"
    theme.mkdir(parents=True)
    target = theme / "requirejs-config.js"
    target.write_text("require.config({});")
    key = "frontend/Magento/luma/en_US/requirejs-config.js"
    value = recorded_hash if recorded_hash is not None else integrity.hash_file(target)
    (area / integrity.HASH_FILE).write_text(json.dumps({key: value}))
    return static, target, key


def test_a_matching_hash_is_left_alone(tmp_path):
    static, _, _ = make_store(tmp_path)
    results = integrity.refresh(static)
    assert results[0].refreshed == []
    assert results[0].unchanged == 1


def test_a_stale_hash_is_refreshed(tmp_path):
    static, _, key = make_store(tmp_path, recorded_hash="sha256-obviouslywrong")
    results = integrity.refresh(static)
    assert results[0].refreshed == [key]
    written = json.loads((static / "frontend" / integrity.HASH_FILE).read_text())
    assert written[key].startswith("sha256-")
    assert written[key] != "sha256-obviouslywrong"


def test_a_dry_run_writes_nothing(tmp_path):
    static, _, key = make_store(tmp_path, recorded_hash="sha256-obviouslywrong")
    integrity.refresh(static, dry_run=True)
    written = json.loads((static / "frontend" / integrity.HASH_FILE).read_text())
    assert written[key] == "sha256-obviouslywrong"


def test_a_hashed_file_that_is_gone_is_reported(tmp_path):
    static, target, key = make_store(tmp_path)
    target.unlink()
    results = integrity.refresh(static)
    assert results[0].missing == [key]


def test_an_unreadable_hash_file_is_an_error(tmp_path):
    static, _, _ = make_store(tmp_path)
    (static / "frontend" / integrity.HASH_FILE).write_text("{not json")
    with pytest.raises(integrity.IntegrityError):
        integrity.refresh(static)
