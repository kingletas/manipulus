"""Decides which modules go in which bundle, and records why each one is there."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .graph import Graph
from .resolve import bundle_id
from .rjsconfig import RequireConfig

COMMON = "common"


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


def build_plan(
    theme: str,
    locale: str,
    graph: Graph,
    config: RequireConfig,
    per_page: dict[str, set[str]],
    entry_sources: dict[str, str] | None = None,
    common_excludes: tuple[str, ...] = ("checkout",),
) -> Plan:
    """Compute the common bundle and one bundle per page type."""
    plan = Plan(theme=theme, locale=locale, entry_sources=dict(entry_sources or {}))

    always, _ = resolve_entries(set(config.deps), config, graph)
    always_closure, always_trace = graph.closure(always)

    closures: dict[str, set[str]] = {}
    traces: dict[str, dict[str, str | None]] = {}
    for page_type, names in per_page.items():
        entries, _missing = resolve_entries(names, config, graph)
        reached, came_from = graph.closure(entries + always)
        closures[page_type] = reached
        traces[page_type] = came_from

    # A module belongs in common when every page type that is allowed to vote loads it.
    voters = [p for p in closures if p not in common_excludes] or list(closures)
    common_modules = set.intersection(*(closures[p] for p in voters)) if voters else set()
    common_modules |= always_closure

    plan.bundles.append(
        Bundle(name=COMMON, modules=sorted(common_modules), page_types=sorted(closures))
    )
    for page_type in sorted(closures):
        remainder = sorted(closures[page_type] - common_modules)
        if remainder:
            plan.bundles.append(Bundle(name=page_type, modules=remainder, page_types=[page_type]))

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


def write(plan: Plan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan.to_json(), encoding="utf-8")
