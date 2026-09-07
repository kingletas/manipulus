"""Decides what a dependency name refers to, and what cannot go in a bundle."""

from __future__ import annotations

import re

REMOTE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:)?//", re.IGNORECASE)

# RequireJS supplies these itself, or Magento loads them outside the AMD graph.
NEVER_BUNDLED = frozenset(
    {
        "require",
        "exports",
        "module",
        # Magento's mixin loader is defined synchronously before any bundle runs.
        "mixins",
        # The legacy Prototype build overwrites native objects; magepack excludes it too.
        "prototype",
        # Written per request by Magento, so a build-time copy would be wrong.
        "js-translation.json",
        "jsbuild",
        "buildTools",
        "statistician",
    }
)

# A plugin whose resource is a real file we can inline. Everything else stays dynamic.
BUNDLABLE_PLUGINS = frozenset({"text"})


def is_remote(name: str) -> bool:
    """True when the name is a URL rather than a module in the deployed tree."""
    return bool(REMOTE.match(name))


def split_plugin(name: str) -> tuple[str | None, str]:
    """Split `text!foo/bar.html` into its plugin and its resource."""
    if "!" not in name:
        return None, name
    plugin, _, resource = name.partition("!")
    return (plugin or None), resource


def bundle_id(name: str) -> str | None:
    """Return the id this dependency has inside a bundle, or None when it cannot be bundled.

    A remote URL, a runtime-generated file and a dynamic plugin resource all stay
    outside the bundle so RequireJS keeps loading them the way it does today.
    """
    if not name or is_remote(name):
        return None
    plugin, resource = split_plugin(name)
    if not resource or is_remote(resource):
        return None
    if resource in NEVER_BUNDLED or name in NEVER_BUNDLED:
        return None
    if plugin is None:
        return resource
    if plugin in BUNDLABLE_PLUGINS:
        return f"{plugin}!{resource}"
    return None
