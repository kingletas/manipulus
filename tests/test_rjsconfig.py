"""The merged requirejs-config.js is many IIFEs, each with its own `var config`."""

from pathlib import Path

import pytest

from manipulus import rjsconfig

TWO_BLOCKS = b"""
(function () {
    var config = { map: { '*': { alpha: 'Vendor_One/js/alpha' } } };
    require.config(config);
})();
(function () {
    var config = { map: { '*': { beta: 'Vendor_Two/js/beta' } }, deps: ['boot'] };
    require.config(config);
})();
"""


def load(tmp_path: Path, source: bytes) -> rjsconfig.RequireConfig:
    target = tmp_path / "requirejs-config.js"
    target.write_bytes(source)
    return rjsconfig.load(target)


def test_each_iife_config_is_read_not_only_the_last(tmp_path):
    """Resolving `config` globally would return the last block for all of them."""
    config = load(tmp_path, TWO_BLOCKS)
    assert config.block_count == 2
    assert config.star_map["alpha"] == "Vendor_One/js/alpha"
    assert config.star_map["beta"] == "Vendor_Two/js/beta"
    assert config.deps == ["boot"]


def test_inline_object_argument_is_read(tmp_path):
    config = load(tmp_path, b"require.config({ paths: { jquery: 'jquery/jquery' } });")
    assert config.paths["jquery"] == "jquery/jquery"


def test_a_file_with_no_config_block_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        load(tmp_path, b"var unrelated = 1;")


def test_map_decides_the_id_and_paths_decides_the_file(tmp_path):
    config = load(
        tmp_path,
        b"require.config({ map: { '*': { ko: 'knockoutjs/knockout' } },"
        b" paths: { knockoutjs: 'lib/knockout' } });",
    )
    assert config.resolve("ko") == "knockoutjs/knockout"
    assert config.path_for("knockoutjs/knockout") == "lib/knockout/knockout"


def test_longest_prefix_wins_for_paths(tmp_path):
    config = load(
        tmp_path,
        b"require.config({ paths: { 'a': 'short', 'a/b': 'long' } });",
    )
    assert config.path_for("a/b/c") == "long/c"
    assert config.path_for("a/z") == "short/z"


def test_scoped_map_beats_star_map(tmp_path):
    config = load(
        tmp_path,
        b"require.config({ map: { '*': { widget: 'default/widget' },"
        b" 'Vendor_Mod': { widget: 'special/widget' } } });",
    )
    assert config.resolve("widget", referrer="Vendor_Mod/js/thing") == "special/widget"
    assert config.resolve("widget", referrer="Other_Mod/js/thing") == "default/widget"


def test_relative_ids_resolve_against_the_referrer(tmp_path):
    config = load(tmp_path, b"require.config({});")
    assert config.resolve("./sibling", referrer="Vendor_Mod/js/thing") == "Vendor_Mod/js/sibling"
    assert config.resolve("../up", referrer="Vendor_Mod/js/deep/thing") == "Vendor_Mod/js/up"


def test_a_disabled_mixin_is_not_collected(tmp_path):
    config = load(
        tmp_path,
        b"require.config({ config: { mixins: { 'target/mod':"
        b" { 'on/mixin': true, 'off/mixin': false } } } });",
    )
    assert config.mixins == {"target/mod": ["on/mixin"]}


def test_paths_decides_the_file_not_the_id(tmp_path):
    """RequireJS asks for `spectrum`; paths only says where its file is."""
    config = load(tmp_path, b"require.config({ paths: { spectrum: 'jquery/spectrum/spectrum' } });")
    assert config.resolve("spectrum") == "spectrum"
    assert config.path_for("spectrum") == "jquery/spectrum/spectrum"


def test_map_still_rewrites_the_id(tmp_path):
    config = load(tmp_path, b"require.config({ map: { '*': { ko: 'knockoutjs/knockout' } } });")
    assert config.resolve("ko") == "knockoutjs/knockout"
