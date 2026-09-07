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


def test_no_module_is_claimed_by_two_bundles(tmp_path):
    """Two bundles claiming one module ship its bytes twice and only one claim wins."""
    from manipulus.plan import Bundle, Plan

    plan = Plan(
        theme="frontend/V/t",
        locale="en_US",
        bundles=[
            Bundle(name="common", modules=["a", "b"]),
            Bundle(name="cart", modules=["c"]),
            Bundle(name="checkout", modules=["d"]),
        ],
    )
    seen: dict[str, int] = {}
    for bundle in plan.bundles:
        for module_id in bundle.modules:
            seen[module_id] = seen.get(module_id, 0) + 1
    assert [m for m, n in seen.items() if n > 1] == []


def test_the_two_common_strategies_differ(tmp_path):
    """Neither answer is free, so the plan records which one produced it."""
    from manipulus.graph import Graph
    from manipulus.plan import build_plan
    from manipulus.rjsconfig import RequireConfig

    graph = Graph()
    for name in ("shared", "only_a", "only_b", "everywhere"):
        graph.files[name] = tmp_path / f"{name}.js"
        graph.edges[name] = []
    config = RequireConfig(raw={}, block_count=1)
    pages = {
        "product": {"shared", "only_a", "everywhere"},
        "cart": {"shared", "only_b", "everywhere"},
        "cms": {"everywhere"},
    }
    intersect = build_plan("t", "en_US", graph, config, pages, common_strategy="intersect")
    promoted = build_plan("t", "en_US", graph, config, pages, common_strategy="shared")

    common_of = lambda p: set(next(b for b in p.bundles if b.name == "common").modules)  # noqa: E731
    assert common_of(intersect) == {"everywhere"}
    assert common_of(promoted) == {"everywhere", "shared"}
    assert intersect.common_strategy == "intersect"


def test_a_bundle_the_plan_no_longer_has_is_removed(tmp_path):
    """A left-behind bundle is still served and reads as current."""
    from manipulus.graph import Graph
    from manipulus.plan import Bundle, Plan

    theme = tmp_path / "theme"
    theme.mkdir()
    module = theme / "a.js"
    module.write_text("define([], function () {});")
    graph = Graph()
    graph.files["a"] = module

    stale = theme / bundler.BUNDLE_DIR / "bundle-gone.js"
    stale.parent.mkdir(parents=True)
    stale.write_text("// from an older plan")

    plan = Plan(theme="t", locale="en_US", bundles=[Bundle(name="common", modules=["a"])])
    bundler.build_bundles(plan, graph, theme)

    assert not stale.exists()
    assert (theme / bundler.BUNDLE_DIR / "bundle-common.js").is_file()


def test_the_magento_module_is_copied_with_its_real_files(tmp_path):
    from manipulus.plan import Bundle, Plan

    plan = Plan(theme="t", locale="en_US", bundles=[Bundle(name="common", modules=["a"])])
    target = tmp_path / "Manipulus" / "Bundles"
    bundler.write_magento_module(plan, target)

    assert (target / "registration.php").is_file()
    assert (target / "etc" / "module.xml").is_file()
    assert (target / "Console" / "Command" / "RefreshIntegrityCommand.php").is_file()
    config = (target / bundler.MODULE_CONFIG).read_text()
    assert "manipulus/bundle-common" in config
    assert "Generated by manipulus" in config
