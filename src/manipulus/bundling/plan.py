"""Decides which modules go in which bundle, and records why each one is there."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..analysis.graph import Graph
from ..analysis.resolve import bundle_id
from ..analysis.rjsconfig import RequireConfig

COMMON = "common"

# Bundles nothing needs before a page can run; RequireJS fetches them on demand.
DEFERRED = "deferred"

# RequireJS keeps one owner per module, so every strategy here has to place a
# module exactly once.
STRATEGIES = ("shared", "cluster")

# Below this, a group of page types does not earn the extra request and its
# modules go to common instead.
CLUSTER_MINIMUM = 10


class PlanError(RuntimeError):
    """A plan was asked for that cannot be expressed as a RequireJS bundles map."""


@dataclass
class Bundle:
    """One bundle: its name, its modules, and the page types that need it."""

    name: str
    modules: list[str] = field(default_factory=list)
    page_types: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """A complete bundling decision for one theme and locale."""

    theme: str
    locale: str
    bundles: list[Bundle] = field(default_factory=list)
    entry_sources: dict[str, str] = field(default_factory=dict)
    reasons: dict[str, list[str]] = field(default_factory=dict)
    unreached: list[str] = field(default_factory=list)
    common_strategy: str = "cluster"
    deferred_count: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> Plan:
        data = json.loads(text)
        bundles = [Bundle(**b) for b in data.pop("bundles", [])]
        return cls(bundles=bundles, **data)

    def bundle_for(self, module_id: str) -> str | None:
        for bundle in self.bundles:
            if module_id in bundle.modules:
                return bundle.name
        return None


def resolve_entries(
    names: set[str], config: RequireConfig, graph: Graph
) -> tuple[list[str], list[str]]:
    """Turn written entry names into module ids, reporting any that match no deployed file."""
    resolved: list[str] = []
    missing: list[str] = []
    for name in sorted(names):
        identifier = bundle_id(config.resolve(name))
        if identifier is None:
            continue
        if identifier in graph.files:
            if identifier not in resolved:
                resolved.append(identifier)
        else:
            missing.append(name)
    return resolved, missing


def _reach(closures: dict[str, set[str]]) -> dict[str, set[str]]:
    """Map each module to the set of page types that load it."""
    reach: dict[str, set[str]] = {}
    for page_type, modules in closures.items():
        for module_id in modules:
            reach.setdefault(module_id, set()).add(page_type)
    return reach


def _verify_single_owner(bundles: list[Bundle]) -> None:
    """Refuse a plan that names one module in two bundles.

    RequireJS builds module-to-bundle from this and keeps the last one it reads, so
    the earlier bundle silently loses the module and pages fetch bundles they never use.
    """
    owners: dict[str, list[str]] = {}
    for bundle in bundles:
        for module_id in bundle.modules:
            owners.setdefault(module_id, []).append(bundle.name)
    clashes = {m: names for m, names in owners.items() if len(names) > 1}
    if clashes:
        example = sorted(clashes)[0]
        raise PlanError(
            f"{len(clashes)} module(s) were placed in more than one bundle, "
            f"for example {example} in {', '.join(clashes[example])}. "
            "A RequireJS bundles map records one owner per module."
        )


def _group(
    closures: dict[str, set[str]],
    always: set[str],
    strategy: str,
    common_excludes: tuple[str, ...],
    cluster_minimum: int,
) -> tuple[set[str], dict[str, set[str]]]:
    """Decide what is shared by everything and what each group of page types shares."""
    reach = _reach(closures)
    shared: dict[str, set[str]] = {}

    if strategy == "shared":
        # Common is what every voting page loads, then anything two or more pages load
        # joins it, so no module is left for two page bundles to claim.
        voters = [p for p in closures if p not in common_excludes] or list(closures)
        common = set.intersection(*(closures[p] for p in voters)) if voters else set()
        common |= always
        common |= {m for m, seen in reach.items() if len(seen) > 1}
        return common, shared

    # Common is what every page loads. Each other group of page types that shares
    # enough modules gets its own bundle, so a page carries only what it can use.
    every_page = set(closures)
    common = set(always)
    common |= {m for m, seen in reach.items() if seen == every_page}

    groups: dict[frozenset[str], set[str]] = {}
    for module_id, seen in reach.items():
        if module_id in common or len(seen) < 2:
            continue
        groups.setdefault(frozenset(seen), set()).add(module_id)

    for seen, modules in groups.items():
        if len(modules) >= cluster_minimum:
            shared["-".join(sorted(seen))] = modules
        else:
            common |= modules

    return common, shared


def build_plan(
    theme: str,
    locale: str,
    graph: Graph,
    config: RequireConfig,
    per_page: dict[str, set[str]],
    entry_sources: dict[str, str] | None = None,
    common_excludes: tuple[str, ...] = ("checkout",),
    common_strategy: str = "cluster",
    cluster_minimum: int = CLUSTER_MINIMUM,
    defer_lazy: bool = False,
) -> Plan:
    """Compute the common bundle, any shared bundles, and one bundle per page type."""
    if common_strategy == "intersect":
        raise PlanError(
            "the intersect strategy cannot be expressed as a RequireJS bundles map, "
            "because a module wanted by two page types would be listed twice and only "
            "the last listing would win. Use shared, or cluster."
        )
    if common_strategy not in STRATEGIES:
        raise PlanError(f"unknown common strategy: {common_strategy}")

    plan = Plan(theme=theme, locale=locale, entry_sources=dict(entry_sources or {}))
    plan.common_strategy = common_strategy

    always, _ = resolve_entries(set(config.deps), config, graph)
    always_closure, always_trace = graph.closure(always)

    closures: dict[str, set[str]] = {}
    boot: dict[str, set[str]] = {}
    traces: dict[str, dict[str, str | None]] = {}
    for page_type, names in per_page.items():
        entries, _missing = resolve_entries(names, config, graph)
        reached, came_from = graph.closure(entries + always)
        closures[page_type] = reached
        boot[page_type] = graph.closure(entries + always, include_lazy=False)[0]
        traces[page_type] = came_from

    # A module nothing needs before it can run goes in a bundle of its own, which
    # RequireJS fetches only when something finally asks for it.
    needed_at_boot = set().union(*boot.values()) if boot else set()
    deferred = (
        {m for page in closures.values() for m in page if m not in needed_at_boot}
        if defer_lazy
        else set()
    )
    plan.deferred_count = len(deferred)

    common_modules, shared_bundles = _group(
        {p: modules - deferred for p, modules in closures.items()},
        always_closure - deferred,
        common_strategy,
        common_excludes,
        cluster_minimum,
    )

    plan.bundles.append(
        Bundle(name=COMMON, modules=sorted(common_modules), page_types=sorted(closures))
    )
    placed = set(common_modules)
    for name in sorted(shared_bundles):
        modules = shared_bundles[name]
        plan.bundles.append(
            Bundle(name=name, modules=sorted(modules), page_types=sorted(name.split("-")))
        )
        placed |= modules

    for page_type in sorted(closures):
        remainder = sorted(closures[page_type] - deferred - placed)
        if remainder:
            plan.bundles.append(Bundle(name=page_type, modules=remainder, page_types=[page_type]))
            placed |= set(remainder)

    if deferred:
        _append_deferred(
            plan, closures, deferred, placed, common_strategy, common_excludes, cluster_minimum
        )

    _verify_single_owner(plan.bundles)

    for page_type, came_from in traces.items():
        for module_id in closures[page_type]:
            plan.reasons.setdefault(module_id, [])
            chain = Graph.trace(came_from, module_id)
            entry = chain[0] if chain else module_id
            marker = f"{page_type}: {entry}"
            if marker not in plan.reasons[module_id]:
                plan.reasons[module_id].append(marker)
    for module_id in always_closure:
        chain = Graph.trace(always_trace, module_id)
        marker = f"always: {chain[0] if chain else module_id}"
        plan.reasons.setdefault(module_id, [])
        if marker not in plan.reasons[module_id]:
            plan.reasons[module_id].insert(0, marker)

    bundled = {m for b in plan.bundles for m in b.modules}
    plan.unreached = sorted(set(graph.files) - bundled)
    return plan


def _append_deferred(
    plan: Plan,
    closures: dict[str, set[str]],
    deferred: set[str],
    placed: set[str],
    strategy: str,
    common_excludes: tuple[str, ...],
    cluster_minimum: int,
) -> None:
    """Group the deferred modules the same way, under names of their own."""
    lazy_closures = {p: modules & deferred for p, modules in closures.items()}
    common, shared = _group(lazy_closures, set(), strategy, common_excludes, cluster_minimum)

    if common:
        plan.bundles.append(
            Bundle(name=DEFERRED, modules=sorted(common), page_types=sorted(closures))
        )
        placed |= common

    for name in sorted(shared):
        plan.bundles.append(
            Bundle(
                name=f"{DEFERRED}-{name}",
                modules=sorted(shared[name]),
                page_types=sorted(name.split("-")),
            )
        )
        placed |= shared[name]

    for page_type in sorted(lazy_closures):
        remainder = sorted(lazy_closures[page_type] - placed)
        if remainder:
            plan.bundles.append(
                Bundle(
                    name=f"{DEFERRED}-{page_type}", modules=remainder, page_types=[page_type]
                )
            )
            placed |= set(remainder)


def write(plan: Plan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan.to_json(), encoding="utf-8")
