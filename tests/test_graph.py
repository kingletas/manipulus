"""Building the graph from a deployed tree, and explaining what it reached."""

from pathlib import Path

import pytest

from manipulus import graph as graph_module
from manipulus import rjsconfig


def theme(tmp_path: Path) -> Path:
    root = tmp_path / "theme"
    (root / "Vendor_Mod" / "js").mkdir(parents=True)
    (root / "Vendor_Mod" / "templates").mkdir(parents=True)
    (root / "requirejs-config.js").write_text(
        "require.config({ map: { '*': { entry: 'Vendor_Mod/js/entry' } },"
        " config: { mixins: { 'Vendor_Mod/js/leaf': { 'Vendor_Mod/js/leaf-mixin': true } } } });"
    )
    entry = root / "Vendor_Mod" / "js" / "entry.js"
    entry.write_text("define(['Vendor_Mod/js/leaf'], function () {});")
    (root / "Vendor_Mod" / "js" / "leaf.js").write_text("define([], function () {});")
    (root / "Vendor_Mod" / "js" / "leaf-mixin.js").write_text("define([], function () {});")
    (root / "Vendor_Mod" / "js" / "orphan.js").write_text("define([], function () {});")
    (root / "Vendor_Mod" / "templates" / "t.html").write_text("<div></div>")
    return root


def build(tmp_path):
    root = theme(tmp_path)
    config = rjsconfig.load(root / "requirejs-config.js")
    return root, config, graph_module.build(root, config, workers=1)


def test_every_deployed_file_becomes_a_module(tmp_path):
    _, _, graph = build(tmp_path)
    assert "Vendor_Mod/js/entry" in graph.files
    assert "text!Vendor_Mod/templates/t.html" in graph.files


def test_a_mixin_is_recorded_as_a_dependency_of_its_target(tmp_path):
    _, _, graph = build(tmp_path)
    assert "Vendor_Mod/js/leaf-mixin" in graph.dependencies("Vendor_Mod/js/leaf")


def test_closure_reaches_through_the_mixin(tmp_path):
    _, config, graph = build(tmp_path)
    reached, _ = graph.closure([config.resolve("entry")])
    assert reached == {
        "Vendor_Mod/js/entry",
        "Vendor_Mod/js/leaf",
        "Vendor_Mod/js/leaf-mixin",
    }


def test_trace_names_the_chain_that_pulled_a_module_in(tmp_path):
    _, config, graph = build(tmp_path)
    _, came_from = graph.closure([config.resolve("entry")])
    assert graph_module.Graph.trace(came_from, "Vendor_Mod/js/leaf-mixin") == [
        "Vendor_Mod/js/entry",
        "Vendor_Mod/js/leaf",
        "Vendor_Mod/js/leaf-mixin",
    ]


def test_an_orphan_is_reached_by_nothing(tmp_path):
    _, config, graph = build(tmp_path)
    reached, _ = graph.closure([config.resolve("entry")])
    assert "Vendor_Mod/js/orphan" not in reached


def test_a_dependency_no_file_backs_is_reported_not_dropped(tmp_path):
    root = theme(tmp_path)
    (root / "Vendor_Mod" / "js" / "entry.js").write_text(
        "define(['registeredAtRuntime'], function () {});"
    )
    config = rjsconfig.load(root / "requirejs-config.js")
    graph = graph_module.build(root, config, workers=1)
    assert "registeredAtRuntime" not in graph.dependencies("Vendor_Mod/js/entry")
    assert "registeredAtRuntime" in graph.external_names


def test_a_missing_theme_is_an_error(tmp_path):
    root = theme(tmp_path)
    parsed = rjsconfig.load(root / "requirejs-config.js")
    with pytest.raises(graph_module.GraphError):
        graph_module.build(tmp_path / "nope", parsed, workers=1)
