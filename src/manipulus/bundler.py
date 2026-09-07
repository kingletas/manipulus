"""Writes the bundle files and the RequireJS configuration that points at them."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .graph import Graph
from .plan import Plan
from .rjsconfig import RequireConfig

BUNDLE_DIR = "manipulus"

NAMED_DEFINE = re.compile(r"(^|[?;\s{}()])define\s*\(\s*['\"]")
ANY_DEFINE = re.compile(r"(^|[?;\s{}()])define\s*\(")


class BundleError(RuntimeError):
    """A bundle could not be written completely."""


@dataclass
class BundleResult:
    name: str
    path: Path
    module_count: int
    bytes_written: int


def _wrap_text_resource(module_id: str, content: str) -> str:
    """A non-JavaScript resource becomes a module returning its own text."""
    return f"define({json.dumps(module_id)}, function () {{ return {json.dumps(content)}; }});\n"


def _wrap_non_amd(module_id: str, content: str) -> str:
    """A plain script becomes a module, taking its dependencies and export from the shim config."""
    name = json.dumps(module_id)
    return (
        f"define({name}, "
        f"(require.s.contexts._.config.shim[{name}] "
        f"&& require.s.contexts._.config.shim[{name}].deps) || [], function () {{\n"
        f"{content}\n"
        f"return (require.s.contexts._.config.shim[{name}] "
        f"&& require.s.contexts._.config.shim[{name}].exportsFn "
        f"&& require.s.contexts._.config.shim[{name}].exportsFn());\n"
        f"}}.bind(window));\n"
    )


def _name_anonymous(module_id: str, content: str) -> str:
    """An anonymous define() has to be given its name before it can share a file."""
    name = json.dumps(module_id)
    return ANY_DEFINE.sub(lambda m: f"{m.group(1)}define({name}, ", content, count=1)


def wrap(module_id: str, path: Path, content: str) -> str:
    if path.suffix != ".js":
        return _wrap_text_resource(module_id, content)
    if not ANY_DEFINE.search(content):
        return _wrap_non_amd(module_id, content)
    if not NAMED_DEFINE.search(content):
        return _name_anonymous(module_id, content)
    return content


def build_bundles(
    plan: Plan,
    graph: Graph,
    theme_root: Path,
    dry_run: bool = False,
) -> list[BundleResult]:
    """Write every bundle in the plan.

    Everything is assembled in memory before anything is written, so a run that cannot
    complete leaves no half-built bundle on disk for RequireJS to find.
    """
    output_dir = theme_root / BUNDLE_DIR
    missing: list[str] = []
    assembled: list[tuple[str, Path, int, str]] = []

    for bundle in plan.bundles:
        pieces: list[str] = []
        for module_id in bundle.modules:
            file = graph.files.get(module_id)
            if file is None or not file.is_file():
                missing.append(f"{bundle.name}: {module_id}")
                continue
            try:
                content = file.read_text("utf-8", errors="replace")
            except OSError as error:
                missing.append(f"{bundle.name}: {module_id} ({error})")
                continue
            pieces.append(wrap(module_id, file, content))
        target = output_dir / f"bundle-{bundle.name}.js"
        assembled.append((bundle.name, target, len(pieces), "\n".join(pieces)))

    if missing:
        listed = "\n  ".join(missing[:10])
        more = f"\n  ... and {len(missing) - 10} more" if len(missing) > 10 else ""
        raise BundleError(
            "refusing to write an incomplete bundle; "
            f"{len(missing)} module(s) could not be read:\n  {listed}{more}"
        )

    results = []
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
    for name, target, count, body in assembled:
        if not dry_run:
            target.write_text(body, encoding="utf-8")
        results.append(
            BundleResult(
                name=name,
                path=target,
                module_count=count,
                bytes_written=len(body.encode("utf-8")),
            )
        )
    return results


def write_requirejs_config(plan: Plan, theme_root: Path, dry_run: bool = False) -> Path:
    """Emit the bundles map so RequireJS fetches a bundle instead of each module."""
    mapping = {
        f"{BUNDLE_DIR}/bundle-{bundle.name}": bundle.modules
        for bundle in plan.bundles
        if bundle.modules
    }
    body = f"require.config({json.dumps({'bundles': mapping}, indent=4, sort_keys=True)});\n"
    target = theme_root / BUNDLE_DIR / "requirejs-bundles-config.js"
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return target


def unused_config(config: RequireConfig) -> dict[str, int]:
    """A quick shape summary, useful when reporting what was read."""
    return {
        "map": len(config.star_map),
        "paths": len(config.paths),
        "shim": len(config.shim),
        "deps": len(config.deps),
        "mixins": len(config.mixins),
    }
