"""Builds the AMD dependency graph by reading every deployed JavaScript file."""

from __future__ import annotations

import os
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .extract import scan_file
from .resolve import bundle_id
from .rjsconfig import RequireConfig

# Files that can live inside a bundle: modules, and text! resources.
BUNDLABLE_SUFFIXES = (".js", ".html")


class GraphError(RuntimeError):
    """A file the graph needs could not be read or parsed."""


@dataclass
class Graph:
    """Every module found in a deployed theme, and what each one depends on."""

    edges: dict[str, list[str]] = field(default_factory=dict)
    files: dict[str, Path] = field(default_factory=dict)
    dynamic: dict[str, list[str]] = field(default_factory=dict)
    external: dict[str, list[str]] = field(default_factory=dict)

    @property
    def external_names(self) -> set[str]:
        """Every dependency left outside the bundles, deduplicated."""
        return {name for names in self.external.values() for name in names}

    def dependencies(self, module_id: str) -> list[str]:
        return self.edges.get(module_id, [])

    @property
    def module_count(self) -> int:
        return len(self.files)

    @property
    def edge_count(self) -> int:
        return sum(len(v) for v in self.edges.values())

    def closure(self, entries: list[str]) -> tuple[set[str], dict[str, str | None]]:
        """Walk out from the entry points, returning what is reachable and how each was reached."""
        reached: set[str] = set()
        came_from: dict[str, str | None] = {}
        queue: deque[str] = deque()
        for entry in entries:
            if entry in reached:
                continue
            reached.add(entry)
            came_from[entry] = None
            queue.append(entry)
        while queue:
            current = queue.popleft()
            for dependency in self.dependencies(current):
                if dependency in reached:
                    continue
                reached.add(dependency)
                came_from[dependency] = current
                queue.append(dependency)
        return reached, came_from

    @staticmethod
    def trace(came_from: dict[str, str | None], module_id: str) -> list[str]:
        """Rebuild the chain from an entry point down to this module."""
        chain: list[str] = []
        current: str | None = module_id
        seen: set[str] = set()
        while current is not None and current not in seen:
            chain.append(current)
            seen.add(current)
            current = came_from.get(current)
        return list(reversed(chain))


def module_id_for(file: Path, theme_root: Path) -> str:
    """The RequireJS id for a deployed file. A text resource keeps its plugin prefix."""
    relative = file.relative_to(theme_root).as_posix()
    if relative.endswith(".html"):
        return f"text!{relative}"
    if relative.endswith(".js"):
        relative = relative[: -len(".js")]
    if relative.endswith(".min"):
        relative = relative[: -len(".min")]
    return relative


def _jobs(theme_root: Path) -> list[tuple[str, str]]:
    """Every bundlable file, paired with the module id it answers to."""
    jobs = []
    for file in sorted(theme_root.rglob("*")):
        if file.is_file() and file.suffix in BUNDLABLE_SUFFIXES:
            jobs.append((module_id_for(file, theme_root), str(file)))
    return jobs


def build(theme_root: Path, config: RequireConfig, workers: int | None = None) -> Graph:
    """Read every .js under a deployed theme and resolve what each module depends on."""
    if not theme_root.is_dir():
        raise GraphError(f"theme directory does not exist: {theme_root}")

    jobs = _jobs(theme_root)
    if not jobs:
        raise GraphError(f"no JavaScript files found under {theme_root}")

    graph = Graph()
    for module_id, path in jobs:
        graph.files[module_id] = Path(path)

    workers = workers or min(os.cpu_count() or 4, 16)
    failures: list[str] = []
    results = []
    if workers > 1 and len(jobs) > 64:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(scan_file, jobs, chunksize=32))
    else:
        results = [scan_file(job) for job in jobs]

    for module_id, names, dynamic, error in results:
        if error:
            failures.append(error)
            continue
        resolved: list[str] = []
        outside: list[str] = []
        for name in [*names, *config.shim_deps(module_id)]:
            target = config.resolve(name, referrer=module_id)
            identifier = bundle_id(target)
            if identifier is None:
                if target not in outside:
                    outside.append(target)
                continue
            if identifier not in resolved:
                resolved.append(identifier)
        graph.edges[module_id] = resolved
        if dynamic:
            graph.dynamic[module_id] = dynamic
        if outside:
            graph.external[module_id] = outside

    if failures:
        listed = "\n  ".join(failures[:10])
        more = f"\n  ... and {len(failures) - 10} more" if len(failures) > 10 else ""
        raise GraphError(f"{len(failures)} file(s) could not be read or parsed:\n  {listed}{more}")

    _apply_mixins(graph, config)
    _partition_unbacked(graph)
    return graph


def _partition_unbacked(graph: Graph) -> None:
    """Move dependencies that no deployed file backs out of the graph and into the report.

    Some modules are registered at runtime by the code that uses them -- PayPal's SDK
    shim is one -- so they are real dependencies with nothing to bundle. They are
    dropped from the edges and listed, never dropped in silence.
    """
    for module_id, targets in graph.edges.items():
        backed = [t for t in targets if t in graph.files]
        if len(backed) == len(targets):
            continue
        unbacked = [t for t in targets if t not in graph.files]
        graph.edges[module_id] = backed
        listed = graph.external.setdefault(module_id, [])
        listed.extend(t for t in unbacked if t not in listed)


def _apply_mixins(graph: Graph, config: RequireConfig) -> None:
    """A mixin loads whenever its target loads, so record it as a dependency of the target."""
    for target, mixins in config.mixins.items():
        resolved_target = bundle_id(config.resolve(target))
        if resolved_target is None:
            continue
        edges = graph.edges.setdefault(resolved_target, [])
        for mixin in mixins:
            identifier = bundle_id(config.resolve(mixin, referrer=resolved_target))
            if identifier and identifier not in edges:
                edges.append(identifier)
