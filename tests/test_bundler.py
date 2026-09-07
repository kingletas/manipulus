"""Writing bundles, and refusing to write one that would be incomplete."""

from pathlib import Path

import pytest

from manipulus import bundler
from manipulus.graph import Graph
from manipulus.plan import Bundle, Plan


def test_a_named_define_is_left_alone():
    source = "define('a/b', [], function () {});"
    assert bundler.wrap("a/b", Path("a/b.js"), source) == source


def test_an_anonymous_define_is_given_its_name():
    wrapped = bundler.wrap("a/b", Path("a/b.js"), "define([], function () {});")
    assert wrapped.startswith('define("a/b", [], function')


def test_only_the_first_define_is_named():
    source = "define([], function () {});\ndefine([], function () {});"
    assert bundler.wrap("a/b", Path("a/b.js"), source).count('define("a/b"') == 1


def test_a_plain_script_is_wrapped_against_its_shim():
    wrapped = bundler.wrap("legacy", Path("legacy.js"), "window.legacy = 1;")
    assert wrapped.startswith('define("legacy"')
    assert "shim" in wrapped


def test_a_text_resource_becomes_a_module_returning_its_text():
    wrapped = bundler.wrap("text!a/b.html", Path("a/b.html"), "<div>hi</div>")
    assert wrapped == 'define("text!a/b.html", function () { return "<div>hi</div>"; });\n'


def _plan_and_graph(tmp_path, module_present: bool):
    theme = tmp_path / "theme"
    theme.mkdir()
    graph = Graph()
    if module_present:
        target = theme / "a.js"
        target.write_text("define([], function () {});")
        graph.files["a"] = target
    else:
        graph.files["a"] = theme / "gone.js"
    bundles = [Bundle(name="common", modules=["a"])]
    plan = Plan(theme="frontend/V/t", locale="en_US", bundles=bundles)
    return plan, graph, theme


def test_a_complete_bundle_is_written(tmp_path):
    plan, graph, theme = _plan_and_graph(tmp_path, module_present=True)
    results = bundler.build_bundles(plan, graph, theme)
    assert results[0].path.is_file()
    assert results[0].module_count == 1


def test_a_missing_module_refuses_the_whole_run(tmp_path):
    """magepack logged this at debug level and reported success. It must not be silent."""
    plan, graph, theme = _plan_and_graph(tmp_path, module_present=False)
    with pytest.raises(bundler.BundleError) as error:
        bundler.build_bundles(plan, graph, theme)
    assert "incomplete" in str(error.value)
    assert not (theme / bundler.BUNDLE_DIR / "bundle-common.js").exists()


def test_a_dry_run_writes_nothing(tmp_path):
    plan, graph, theme = _plan_and_graph(tmp_path, module_present=True)
    bundler.build_bundles(plan, graph, theme, dry_run=True)
    assert not (theme / bundler.BUNDLE_DIR).exists()


def test_the_requirejs_config_maps_each_bundle_to_its_modules(tmp_path):
    plan, _, theme = _plan_and_graph(tmp_path, module_present=True)
    target = bundler.write_requirejs_config(plan, theme)
    body = target.read_text()
    assert "manipulus/bundle-common" in body
    assert '"a"' in body
