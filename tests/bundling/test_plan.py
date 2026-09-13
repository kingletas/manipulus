"""The planner has to place every module exactly once, whatever strategy it is asked for."""

from __future__ import annotations

import pytest

from manipulus.analysis.graph import Graph
from manipulus.analysis.rjsconfig import RequireConfig
from manipulus.bundling.plan import Bundle, PlanError, _verify_single_owner, build_plan


def _graph(tmp_path, names):
    graph = Graph()
    for name in names:
        graph.files[name] = tmp_path / f"{name}.js"
        graph.edges[name] = []
    return graph


def _common(plan):
    return set(next(b for b in plan.bundles if b.name == "common").modules)


def _named(plan, name):
    return set(next(b for b in plan.bundles if b.name == name).modules)


def test_intersect_is_refused_because_requirejs_keeps_one_owner(tmp_path):
    """It would list a module under two bundles, and only the last listing would win."""
    graph = _graph(tmp_path, ["a"])
    config = RequireConfig(raw={}, block_count=1)

    with pytest.raises(PlanError, match="last listing would win"):
        build_plan("t", "en_US", graph, config, {"cms": {"a"}}, common_strategy="intersect")


def test_an_unknown_strategy_is_refused(tmp_path):
    graph = _graph(tmp_path, ["a"])
    config = RequireConfig(raw={}, block_count=1)

    with pytest.raises(PlanError, match="unknown common strategy"):
        build_plan("t", "en_US", graph, config, {"cms": {"a"}}, common_strategy="nonsense")


def test_a_module_in_two_bundles_is_refused(tmp_path):
    """The check that stands between a plan and an unusable bundles map."""
    with pytest.raises(PlanError, match="more than one bundle"):
        _verify_single_owner(
            [Bundle(name="cart", modules=["a"]), Bundle(name="checkout", modules=["a"])]
        )


def test_cluster_gives_a_shared_group_its_own_bundle(tmp_path):
    """Modules two pages share belong to those two pages, not to every page."""
    names = ["everywhere", "both", "only_cart", "only_checkout"] + [f"pair{i}" for i in range(10)]
    graph = _graph(tmp_path, names)
    config = RequireConfig(raw={}, block_count=1)
    pair = {f"pair{i}" for i in range(10)}
    pages = {
        "cart": {"everywhere", "only_cart", *pair},
        "checkout": {"everywhere", "only_checkout", *pair},
        "cms": {"everywhere"},
    }

    plan = build_plan("t", "en_US", graph, config, pages, common_strategy="cluster")

    assert _common(plan) == {"everywhere"}
    assert _named(plan, "cart-checkout") == pair
    assert _named(plan, "cart") == {"only_cart"}
    assert _named(plan, "checkout") == {"only_checkout"}


def test_a_group_too_small_to_earn_a_request_goes_to_common(tmp_path):
    """One extra file for two modules costs more than carrying them everywhere."""
    graph = _graph(tmp_path, ["everywhere", "pair_a", "pair_b"])
    config = RequireConfig(raw={}, block_count=1)
    pages = {
        "cart": {"everywhere", "pair_a", "pair_b"},
        "checkout": {"everywhere", "pair_a", "pair_b"},
        "cms": {"everywhere"},
    }

    plan = build_plan("t", "en_US", graph, config, pages, common_strategy="cluster")

    assert _common(plan) == {"everywhere", "pair_a", "pair_b"}
    assert [b.name for b in plan.bundles] == ["common"]


def test_the_cluster_minimum_is_the_caller_s_to_set(tmp_path):
    graph = _graph(tmp_path, ["everywhere", "pair_a", "pair_b"])
    config = RequireConfig(raw={}, block_count=1)
    pages = {
        "cart": {"everywhere", "pair_a", "pair_b"},
        "checkout": {"everywhere", "pair_a", "pair_b"},
        "cms": {"everywhere"},
    }

    plan = build_plan(
        "t", "en_US", graph, config, pages, common_strategy="cluster", cluster_minimum=2
    )

    assert _named(plan, "cart-checkout") == {"pair_a", "pair_b"}


def test_shared_puts_everything_two_pages_load_in_common(tmp_path):
    graph = _graph(tmp_path, ["everywhere", "both", "only_a"])
    config = RequireConfig(raw={}, block_count=1)
    pages = {
        "product": {"everywhere", "both", "only_a"},
        "cart": {"everywhere", "both"},
        "cms": {"everywhere"},
    }

    plan = build_plan("t", "en_US", graph, config, pages, common_strategy="shared")

    assert _common(plan) == {"everywhere", "both"}
    assert _named(plan, "product") == {"only_a"}


def test_every_strategy_places_each_module_exactly_once(tmp_path):
    """The property the whole map depends on, asserted for both strategies."""
    names = ["everywhere", "only_cms"] + [f"pair{i}" for i in range(12)]
    graph = _graph(tmp_path, names)
    config = RequireConfig(raw={}, block_count=1)
    pair = {f"pair{i}" for i in range(12)}
    pages = {
        "cart": {"everywhere", *pair},
        "checkout": {"everywhere", *pair},
        "cms": {"everywhere", "only_cms"},
    }

    for strategy in ("cluster", "shared"):
        plan = build_plan("t", "en_US", graph, config, pages, common_strategy=strategy)
        seen: dict[str, int] = {}
        for bundle in plan.bundles:
            for module_id in bundle.modules:
                seen[module_id] = seen.get(module_id, 0) + 1
        assert [m for m, n in seen.items() if n > 1] == [], strategy
