"""Reads Magento's merged requirejs-config.js and resolves module names the way RequireJS does."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import jsparse

CONFIG_CALLS = {"require.config", "requirejs.config", "require.s.contexts._.config"}


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    for key, value in source.items():
        existing = target.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            _deep_merge(existing, value)
        elif isinstance(value, list) and isinstance(existing, list):
            target[key] = existing + [item for item in value if item not in existing]
        else:
            target[key] = value
    return target


def split_plugin(name: str) -> tuple[str | None, str]:
    """Split `text!foo/bar.html` into its plugin and its resource."""
    if "!" not in name:
        return None, name
    plugin, _, resource = name.partition("!")
    return plugin, resource


def normalise(name: str, referrer: str | None) -> str:
    """Resolve a relative module id against the module that asked for it."""
    if not name.startswith("."):
        return name
    base = posixpath.dirname(referrer) if referrer else ""
    return posixpath.normpath(posixpath.join(base, name)).lstrip("./")


@dataclass
class RequireConfig:
    """The merged RequireJS configuration for one theme and locale."""

    raw: dict[str, Any] = field(default_factory=dict)
    block_count: int = 0

    @property
    def star_map(self) -> dict[str, str]:
        entries = self.raw.get("map", {}).get("*", {})
        return {k: v for k, v in entries.items() if isinstance(v, str)}

    @property
    def scoped_map(self) -> dict[str, dict[str, str]]:
        out = {}
        for scope, entries in self.raw.get("map", {}).items():
            if scope == "*" or not isinstance(entries, dict):
                continue
            out[scope] = {k: v for k, v in entries.items() if isinstance(v, str)}
        return out

    @property
    def paths(self) -> dict[str, str]:
        return {k: v for k, v in self.raw.get("paths", {}).items() if isinstance(v, str)}

    @property
    def shim(self) -> dict[str, Any]:
        return self.raw.get("shim", {})

    @property
    def deps(self) -> list[str]:
        """Modules RequireJS loads on every page without being asked."""
        return [d for d in self.raw.get("deps", []) if isinstance(d, str)]

    @property
    def mixins(self) -> dict[str, list[str]]:
        """Target module id to the mixin module ids that are enabled for it."""
        out: dict[str, list[str]] = {}
        declared = self.raw.get("config", {}).get("mixins", {})
        if not isinstance(declared, dict):
            return out
        for target, entries in declared.items():
            if not isinstance(entries, dict):
                continue
            enabled = [mixin for mixin, on in entries.items() if on is True]
            if enabled:
                out[target] = enabled
        return out

    def shim_deps(self, module_id: str) -> list[str]:
        entry = self.shim.get(module_id)
        if isinstance(entry, list):
            return [d for d in entry if isinstance(d, str)]
        if isinstance(entry, dict):
            return [d for d in entry.get("deps", []) if isinstance(d, str)]
        return []

    def resolve(self, name: str, referrer: str | None = None) -> str:
        """Turn a written module name into the id RequireJS would load."""
        plugin, resource = split_plugin(name)
        resource = normalise(resource, referrer)
        resource = self._apply_map(resource, referrer)
        resource = self._apply_paths(resource)
        return f"{plugin}!{resource}" if plugin else resource

    def _apply_map(self, name: str, referrer: str | None) -> str:
        if referrer:
            for scope in sorted(self.scoped_map, key=len, reverse=True):
                if referrer == scope or referrer.startswith(scope + "/"):
                    mapped = self._longest_prefix(self.scoped_map[scope], name)
                    if mapped is not None:
                        return mapped
        mapped = self._longest_prefix(self.star_map, name)
        return mapped if mapped is not None else name

    def _apply_paths(self, name: str) -> str:
        mapped = self._longest_prefix(self.paths, name)
        return mapped if mapped is not None else name

    @staticmethod
    def _longest_prefix(table: dict[str, str], name: str) -> str | None:
        """Apply the longest matching prefix rule RequireJS uses for map and paths."""
        best: str | None = None
        best_len = -1
        for key, value in table.items():
            if name == key:
                if len(key) > best_len:
                    best, best_len = value, len(key)
            elif name.startswith(key + "/") and len(key) > best_len:
                best, best_len = value + name[len(key) :], len(key)
        return best


def load(path: Path) -> RequireConfig:
    """Parse a merged requirejs-config.js into one configuration."""
    source = path.read_bytes()
    root = jsparse.parse(source)
    merged: dict[str, Any] = {}
    blocks = 0
    for call in jsparse.calls_named(root, source, CONFIG_CALLS):
        target = jsparse.resolve_object_argument(call, source)
        if target is None:
            continue
        value = jsparse.literal(target, source)
        if isinstance(value, dict):
            _deep_merge(merged, value)
            blocks += 1
    if blocks == 0:
        raise ValueError(f"no require.config() blocks found in {path}")
    return RequireConfig(raw=merged, block_count=blocks)
