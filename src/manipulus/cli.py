"""Command line entry point for manipulus."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, bundler, entrypoints, rjsconfig
from . import graph as graph_module
from . import plan as plan_module

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
    )
    out = Path(args.out).expanduser()
    plan_module.write(plan, out)

    print(f"plan written to {out}")
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

    verb = "would write" if args.dry_run else "wrote"
    total = 0
    for result in results:
        total += result.bytes_written
        size = result.bytes_written / 1024
        print(f"  {verb} {result.path.name:28s} {result.module_count:5d} modules  {size:8.0f} kB")
    print(f"  {verb} {config_file.name}")
    print(f"  total {total / 1024:.0f} kB")
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
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("build", parents=[common, planned], help="Write the bundles")
    p.add_argument("-n", "--dry-run", action="store_true", help="report without writing")
    p.set_defaults(func=cmd_build)

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
        graph_module.GraphError,
        bundler.BundleError,
        entrypoints.EntryPointError,
        ValueError,
    ) as error:
        print(f"manipulus: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
