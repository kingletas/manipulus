"""Command line entry point for manipulus."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .analysis import entrypoints, rjsconfig, stylesheets
from .analysis import graph as graph_module
from .bundling import bundler
from .bundling import plan as plan_module
from .magento import integrity

DEFAULT_PLAN = "manipulus.plan.json"


def theme_root_for(root: Path, theme: str, locale: str) -> Path:
    return root / "pub" / "static" / theme / locale


def load_config_and_graph(
    args,
) -> tuple[rjsconfig.RequireConfig, graph_module.Graph, Path]:
    theme_root = theme_root_for(Path(args.root).expanduser(), args.theme, args.locale)
    config_file = theme_root / "requirejs-config.js"
    if not config_file.is_file():
        raise SystemExit(
            f"manipulus: no requirejs-config.js at {config_file}\n"
            "Deploy static content for this theme and locale first."
        )
    config = rjsconfig.load(config_file)
    graph = graph_module.build(theme_root, config, workers=args.jobs)
    return config, graph, theme_root


def collect_entry_points(args, config, graph) -> tuple[dict[str, set[str]], dict[str, str]]:
    """Gather entry points per page type, static first and HTTP on top where a URL was given."""
    source_roots = [Path(args.root).expanduser() / part for part in ("app/code", "vendor")]
    urls = dict(pair.split("=", 1) for pair in (args.url or []))
    per_page: dict[str, set[str]] = {}
    sources: dict[str, str] = {}

    index = entrypoints.SourceIndex(source_roots)
    for page_type in entrypoints.PAGE_TYPES:
        found = entrypoints.from_templates(page_type, source_roots, index=index)
        source = "static"
        if page_type in urls:
            html = entrypoints.fetch(urls[page_type], timeout=args.timeout)
            harvested = entrypoints.from_html(html, page_type, urls[page_type])
            found.names |= harvested.names
            source = "static+html"
        per_page[page_type] = found.names
        sources[page_type] = source
    return per_page, sources


def cmd_graph(args) -> int:
    config, graph, theme_root = load_config_and_graph(args)
    print(f"theme          {theme_root}")
    print(f"config blocks  {config.block_count}")
    shape = bundler.unused_config(config)
    print(f"config shape   map {shape['map']}  paths {shape['paths']}  "
          f"shim {shape['shim']}  deps {shape['deps']}  mixins {shape['mixins']}")
    print(f"modules        {graph.module_count}")
    print(f"edges          {graph.edge_count}")
    print(f"dynamic deps   {len(graph.dynamic)} file(s) name a dependency this cannot resolve")
    external = graph.external_names
    print(f"external       {len(external)} dependencies left outside bundles "
          f"(remote URLs, runtime-registered, generated)")
    if args.verbose and external:
        for name in sorted(external)[:20]:
            print(f"  {name}")
    if args.verbose and graph.dynamic:
        for module_id, expressions in sorted(graph.dynamic.items())[:20]:
            print(f"  {module_id}: {', '.join(expressions[:2])}")
    return 0


def cmd_plan(args) -> int:
    config, graph, theme_root = load_config_and_graph(args)
    per_page, sources = collect_entry_points(args, config, graph)
    plan = plan_module.build_plan(
        theme=args.theme,
        locale=args.locale,
        graph=graph,
        config=config,
        per_page=per_page,
        entry_sources=sources,
        common_strategy=args.common,
    )
    out = Path(args.out).expanduser()
    plan_module.write(plan, out)

    print(f"plan written to {out}   (common: {args.common})")
    for bundle in plan.bundles:
        origin = sources.get(bundle.name, "derived")
        print(f"  {bundle.name:12s} {len(bundle.modules):5d} modules   ({origin})")
    print(f"  {'unbundled':12s} {len(plan.unreached):5d} modules reached by no page type")
    return 0


def cmd_build(args) -> int:
    config, graph, theme_root = load_config_and_graph(args)
    plan_path = Path(args.plan).expanduser()
    if not plan_path.is_file():
        raise SystemExit(f"manipulus: no plan at {plan_path}. Run `manipulus plan` first.")
    plan = plan_module.Plan.from_json(plan_path.read_text("utf-8"))

    results = bundler.build_bundles(plan, graph, theme_root, dry_run=args.dry_run)
    config_file = bundler.write_requirejs_config(plan, theme_root, dry_run=args.dry_run)
    module_dir = None
    if args.module:
        module_dir = bundler.write_magento_module(
            plan, Path(args.module).expanduser(), dry_run=args.dry_run
        )

    verb = "would write" if args.dry_run else "wrote"
    total = 0
    for result in results:
        total += result.bytes_written
        size = result.bytes_written / 1024
        print(f"  {verb} {result.path.name:28s} {result.module_count:5d} modules  {size:8.0f} kB")
    print(f"  {verb} {config_file.name}")
    if module_dir is not None:
        print(f"  {verb} {bundler.MODULE_NAME} into {module_dir}")
        print(f"         enable it with: bin/magento module:enable {bundler.MODULE_NAME}")
    print(f"  total {total / 1024:.0f} kB")
    return 0


def cmd_css(args) -> int:
    """Report the CSS a theme deploys, and how much of it a page plausibly uses."""
    theme_root = theme_root_for(Path(args.root).expanduser(), args.theme, args.locale)
    sheets = stylesheets.read_theme(theme_root)
    if not sheets:
        print(f"manipulus: no stylesheets under {theme_root}", file=sys.stderr)
        return 1

    total_bytes = sum(s.bytes_on_disk for s in sheets)
    total_rules = sum(s.rule_count for s in sheets)
    print(f"{len(sheets)} stylesheet(s), {total_bytes / 1024:.0f} kB, {total_rules} rules")
    for sheet in sorted(sheets, key=lambda s: -s.bytes_on_disk)[: args.top]:
        print(f"  {sheet.kilobytes:8.0f} kB  {sheet.rule_count:6d} rules  {sheet.relative}")

    for url in args.url or []:
        html = entrypoints.fetch(url, timeout=args.timeout)
        linked = stylesheets.linked_stylesheets(html)
        print()
        print(f"{url}")
        print(f"  links {len(linked)} stylesheet(s)")
        by_name = {s.relative.split("/")[-1]: s for s in sheets}
        names = (href.split("/")[-1].split("?")[0] for href in linked)
        loaded = [by_name[name] for name in names if name in by_name]
        if loaded:
            served = sum(s.bytes_on_disk for s in loaded)
            print(f"  {served / 1024:.0f} kB of CSS served on this page")
        for row in sorted(stylesheets.coverage(loaded, html), key=lambda c: c.percent):
            print(
                f"    {row.percent:5.1f}%  {row.classes_present:5d}/{row.classes_in_css:<5d}"
                f" class names present   {row.stylesheet}"
            )
        print("  Class names only: a rule whose classes are absent may still be used by")
        print("  JavaScript at runtime, so treat a low number as a question, not a verdict.")
    return 0


def cmd_sri(args) -> int:
    """Recompute Magento's subresource integrity hashes for the deployed static files."""
    static_root = Path(args.root).expanduser() / "pub" / "static"
    results = integrity.refresh(static_root, dry_run=args.dry_run)
    if not results:
        print(f"manipulus: no {integrity.HASH_FILE} under {static_root}", file=sys.stderr)
        return 1
    verb = "would refresh" if args.dry_run else "refreshed"
    total = 0
    for result in results:
        total += len(result.refreshed)
        for key in result.refreshed:
            print(f"  {verb} {key}")
        for key in result.missing:
            print(f"  hashed but not deployed: {key}", file=sys.stderr)
    if total == 0:
        return 0
    print(f"  {total} hash(es) {verb}")
    return 0


def cmd_explain(args) -> int:
    plan_path = Path(args.plan).expanduser()
    if not plan_path.is_file():
        raise SystemExit(f"manipulus: no plan at {plan_path}. Run `manipulus plan` first.")
    plan = plan_module.Plan.from_json(plan_path.read_text("utf-8"))
    module_id = args.module
    bundle = plan.bundle_for(module_id)
    if bundle is None:
        print(f"{module_id} is in no bundle.")
        return 1
    print(f"{module_id}")
    print(f"  bundle: {bundle}")
    for reason in plan.reasons.get(module_id, []):
        print(f"  reached by {reason}")
    return 0


def cmd_check(args) -> int:
    """Report only what is wrong. Silence means the plan and the theme agree."""
    config, graph, theme_root = load_config_and_graph(args)
    plan_path = Path(args.plan).expanduser()
    if not plan_path.is_file():
        print(f"manipulus: no plan at {plan_path}", file=sys.stderr)
        return 1
    plan = plan_module.Plan.from_json(plan_path.read_text("utf-8"))

    findings: list[str] = []
    for bundle in plan.bundles:
        for module_id in bundle.modules:
            if module_id not in graph.files:
                findings.append(f"{bundle.name}: {module_id} is planned but not deployed")
    if plan.theme != args.theme or plan.locale != args.locale:
        findings.append(
            f"plan is for {plan.theme}/{plan.locale}, asked about {args.theme}/{args.locale}"
        )

    for finding in findings:
        print(f"manipulus: {finding}", file=sys.stderr)
    return 1 if findings else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manipulus",
        description="Static RequireJS bundle planner for Magento 2. No browser, no Node.",
    )
    parser.add_argument("--version", action="version", version=f"manipulus {__version__}")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".", help="Magento installation root")
    common.add_argument("--theme", default="frontend/Magento/luma", help="area/Vendor/theme")
    common.add_argument("--locale", default="en_US", help="deployed locale")
    common.add_argument(
        "--jobs", type=int, default=None, help="parallel workers (default: cpu count)"
    )

    planned = argparse.ArgumentParser(add_help=False)
    planned.add_argument("--plan", default=DEFAULT_PLAN, help="path to the plan file")

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("graph", parents=[common], help="Report the dependency graph")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_graph)

    p = sub.add_parser("plan", parents=[common], help="Decide the bundles")
    p.add_argument("--out", default=DEFAULT_PLAN)
    p.add_argument(
        "--url",
        action="append",
        metavar="TYPE=URL",
        help="sharpen one page type from rendered HTML, e.g. product=https://store/p.html",
    )
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument(
        "--common",
        choices=["intersect", "shared"],
        default="intersect",
        help="what goes in the common bundle: only what every page loads (intersect, "
        "the default), or anything two or more pages load (shared)",
    )
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("build", parents=[common, planned], help="Write the bundles")
    p.add_argument("-n", "--dry-run", action="store_true", help="report without writing")
    p.add_argument(
        "--module",
        metavar="DIR",
        help="also emit a Magento module that contributes the bundles map, "
        "e.g. app/code/Manipulus/Bundles",
    )
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("css", parents=[common], help="Report deployed CSS and its plausible use")
    p.add_argument("--url", action="append", metavar="URL", help="also analyse a rendered page")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--top", type=int, default=8, help="how many stylesheets to list")
    p.set_defaults(func=cmd_css)

    p = sub.add_parser(
        "sri",
        parents=[],
        help="Refresh Magento's subresource integrity hashes after a static file changes",
    )
    p.add_argument("--root", default=".", help="Magento installation root")
    p.add_argument("-n", "--dry-run", action="store_true", help="report without writing")
    p.set_defaults(func=cmd_sri)

    p = sub.add_parser("explain", parents=[planned], help="Say why a module is bundled")
    p.add_argument("module")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("check", parents=[common, planned], help="Silent unless the plan is stale")
    p.set_defaults(func=cmd_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (
        integrity.IntegrityError,
        graph_module.GraphError,
        bundler.BundleError,
        entrypoints.EntryPointError,
        ValueError,
    ) as error:
        print(f"manipulus: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
