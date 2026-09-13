"""Checks what is actually deployed, rather than what a plan says should be."""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

BUNDLE_CONFIG = "manipulus/requirejs-bundles-config.js"

# `define("some/module", ...)` and `define('some/module', ...)`.
_DEFINE = re.compile(r"""define\(\s*(['"])(?P<id>[^'"]+)\1""")

# The map manipulus writes is JSON inside one require.config call.
_BUNDLES = re.compile(r'"bundles"\s*:\s*(?P<map>\{.*\})\s*\}\s*\)\s*;?\s*$', re.S)

_SCRIPT_SRC = re.compile(r"""<script[^>]+src=(['"])(?P<src>[^'"]+)\1""", re.I)


class DeployedError(RuntimeError):
    """Something that has to be readable to check anything else could not be read."""


def bundles_map(text: str) -> dict[str, list[str]]:
    """The module-to-bundle map out of a deployed RequireJS bundles config."""
    match = _BUNDLES.search(text.strip())
    if match is None:
        raise DeployedError("no bundles map in the config: it is not one this tool wrote")
    try:
        parsed = json.loads(match.group("map"))
    except json.JSONDecodeError as error:
        raise DeployedError(f"the bundles map is not valid JSON: {error}") from error
    return {name: list(modules) for name, modules in parsed.items()}


def defined_modules(text: str) -> set[str]:
    """Every module id a bundle file actually defines."""
    return {m.group("id") for m in _DEFINE.finditer(text)}


def verify_bundles(theme_root: Path) -> list[str]:
    """Every module the map claims is defined by the bundle that claims it.

    RequireJS waits for a module its map promised, so a bundle that over-claims leaves a
    component half-built with nothing in the console.
    """
    config = theme_root / BUNDLE_CONFIG
    if not config.is_file():
        raise DeployedError(f"no bundles config at {config}")

    findings: list[str] = []
    for name, claimed in bundles_map(config.read_text("utf-8")).items():
        file = theme_root / f"{name}.js"
        if not file.is_file():
            findings.append(f"{name}: the map names this bundle and no file is deployed for it")
            continue
        missing = [m for m in claimed if m not in defined_modules(file.read_text("utf-8"))]
        if missing:
            listed = ", ".join(sorted(missing)[:3])
            more = f" and {len(missing) - 3} more" if len(missing) > 3 else ""
            findings.append(
                f"{name}: claims {len(missing)} module(s) it does not define, "
                f"for example {listed}{more}"
            )
    return findings


def verify_page(url: str, timeout: float = 30.0) -> list[str]:
    """Every script a rendered page asks for is one the server will hand over."""
    findings: list[str] = []
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            page = response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as error:
        raise DeployedError(f"could not fetch {url}: {error}") from error

    # Magento writes a script URL with its punctuation escaped, so it is not a URL
    # until it is unescaped.
    sources = {html.unescape(m.group("src")) for m in _SCRIPT_SRC.finditer(page)}
    for source in sorted(sources):
        # Somebody else's CDN is not this deploy's to answer for.
        if ("://" in source or source.startswith("//")) and not source.startswith(_origin(url)):
            continue
        status = _status(_absolute(source, url), timeout)
        if status != 200:
            findings.append(f"{url} asks for {source} and the server answers {status}")
    return findings


def _origin(url: str) -> str:
    parts = url.split("/", 3)
    return "/".join(parts[:3]) if len(parts) > 2 else url


def _absolute(source: str, page: str) -> str:
    if "://" in source:
        return source
    if source.startswith("//"):
        return page.split(":", 1)[0] + ":" + source
    if source.startswith("/"):
        return _origin(page) + source
    return page.rsplit("/", 1)[0] + "/" + source


def _status(url: str, timeout: float) -> int | str:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status)
    except urllib.error.HTTPError as error:
        return int(error.code)
    except (urllib.error.URLError, OSError) as error:
        return f"no answer ({error})"
