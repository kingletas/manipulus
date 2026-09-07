"""Finds the module names a page asks for, from the codebase and from rendered HTML."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from xml.etree.ElementTree import ParseError

from defusedxml.common import DefusedXmlException

# Layout XML comes out of vendor/, which is arbitrary third-party code, so it is parsed
# with entity and DTD handling switched off. The stock parser will follow an external
# entity off the filesystem and will expand a billion-laughs bomb.
from defusedxml.ElementTree import parse as parse_xml

# The layout handle Magento renders for each page type we plan a bundle for.
PAGE_TYPES: dict[str, str] = {
    "cms": "cms_index_index",
    "category": "catalog_category_view",
    "product": "catalog_product_view",
    "cart": "checkout_cart_index",
    "checkout": "checkout_index_index",
}

# Every page gets these two on top of its own handle.
BASE_HANDLES = ("default", "default_head_blocks")

COMPONENT_KEY = r"""["']([A-Za-z_][\w]*(?:_[\w]+)?/[\w./-]+)["']\s*:"""

INIT_BLOCK = re.compile(
    r"<script[^>]+type=[\"']text/x-magento-init[\"'][^>]*>(.*?)</script>",
    re.DOTALL | re.IGNORECASE,
)


class EntryPointError(RuntimeError):
    """Entry points could not be collected from the source that was asked for."""


@dataclass
class EntryPoints:
    """The module names one page type asks for, and where each name was found."""

    page_type: str
    names: set[str] = field(default_factory=set)
    source: str = "static"
    detail: dict[str, str] = field(default_factory=dict)

    def add(self, name: str, found_in: str) -> None:
        if not name or name.startswith("#") or name.startswith("."):
            return
        self.names.add(name)
        self.detail.setdefault(name, found_in)


def _component_names(payload: object) -> Iterator[str]:
    """Walk an x-magento-init payload, yielding every component name it names."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            # Under a CSS selector, each key is a component name.
            if isinstance(value, dict) and key not in ("config", "children", "components"):
                yield key
            if key == "component" and isinstance(value, str):
                yield value
            yield from _component_names(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _component_names(item)


class _ScriptCollector(HTMLParser):
    """Collects x-magento-init payloads and data-mage-init attributes from rendered HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.payloads: list[str] = []
        self._capturing = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        inline = attributes.get("data-mage-init")
        if inline:
            self.payloads.append(inline)
        if tag == "script" and attributes.get("type") == "text/x-magento-init":
            self._capturing = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._capturing = False

    def handle_data(self, data: str) -> None:
        if self._capturing and data.strip():
            self.payloads.append(data)


def from_html(html: str, page_type: str, origin: str) -> EntryPoints:
    """Harvest every entry point out of server-rendered HTML. No JavaScript is executed."""
    found = EntryPoints(page_type=page_type, source="html")
    collector = _ScriptCollector()
    collector.feed(html)
    payloads = list(collector.payloads)
    # The parser drops a payload when a script body contains markup-like text, so sweep too.
    payloads.extend(match.group(1) for match in INIT_BLOCK.finditer(html))

    for payload in payloads:
        text = payload.strip()
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        for name in _component_names(data):
            found.add(name, origin)
    return found


def fetch(url: str, timeout: float = 30.0, user_agent: str = "manipulus") -> str:
    """Fetch a page over plain HTTP. No browser, and nothing on the page is run."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, "replace")
    except urllib.error.URLError as error:
        raise EntryPointError(f"could not fetch {url}: {error}") from error


def components_in_layout(layout: Path) -> set[str]:
    """Read the UI component names a layout declares in its jsLayout arguments.

    Magento renders these through getJsLayout() at runtime, so the template only shows
    a PHP call. The names themselves are right here in the XML.
    """
    try:
        tree = parse_xml(layout)
    except (ParseError, DefusedXmlException, OSError):
        return set()
    found = set()
    for element in tree.iter():
        if element.get("name") != "component":
            continue
        value = (element.text or "").strip()
        if value and "/" in value:
            found.add(value)
    return found


def templates_in_layout(layout: Path) -> set[str]:
    """Read the template references out of one layout XML file."""
    try:
        tree = parse_xml(layout)
    except (ParseError, DefusedXmlException, OSError):
        return set()
    found = set()
    for element in tree.iter():
        template = element.get("template")
        if template:
            found.add(template)
    return found


class SourceIndex:
    """Every frontend template and layout file on disk, found in one walk.

    Both lookups used to re-walk the tree per page type, which is a tree walk inside a
    loop and cost more than the whole graph build.
    """

    def __init__(self, source_roots: list[Path]) -> None:
        self.templates_by_module: dict[tuple[str, str], Path] = {}
        self.templates_by_relative: dict[str, Path] = {}
        self.layouts: dict[str, list[Path]] = {}
        for root in source_roots:
            if not root.is_dir():
                continue
            self._index_root(root)

    def _index_root(self, root: Path) -> None:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            posix = path.as_posix()
            if path.suffix == ".phtml" and "/view/frontend/templates/" in posix:
                package, relative = posix.split("/view/frontend/templates/", 1)
                module = _module_name_for(Path(package))
                if module:
                    self.templates_by_module.setdefault((module, relative), path)
                self.templates_by_relative.setdefault(relative, path)
            elif path.suffix == ".xml" and "/layout/" in posix and "/frontend/" in posix:
                self.layouts.setdefault(path.name, []).append(path)

    def resolve_template(self, reference: str) -> Path | None:
        """Turn `Magento_Catalog::product/view/foo.phtml` into a file on disk."""
        if "::" in reference:
            module, _, relative = reference.partition("::")
            found = self.templates_by_module.get((module, relative))
            if found is not None:
                return found
            return self.templates_by_relative.get(relative)
        return self.templates_by_relative.get(reference)

    def layouts_for(self, handles: list[str]) -> list[Path]:
        found: list[Path] = []
        for handle in handles:
            found.extend(self.layouts.get(f"{handle}.xml", []))
        return sorted(set(found))

    @property
    def template_count(self) -> int:
        return len(self.templates_by_relative)

    @property
    def layout_count(self) -> int:
        return sum(len(v) for v in self.layouts.values())


def _module_name_for(package_dir: Path) -> str | None:
    """Read the Magento module name a package declares, falling back to its directory name."""
    registration = package_dir / "registration.php"
    if registration.is_file():
        try:
            text = registration.read_text("utf-8", errors="replace")
        except OSError:
            text = ""
        match = re.search(r"['\"]([A-Z][A-Za-z0-9]*_[A-Za-z0-9]+)['\"]", text)
        if match:
            return match.group(1)
    name = package_dir.name
    if name.startswith("module-"):
        vendor = package_dir.parent.name
        rest = "".join(part.capitalize() for part in name[len("module-"):].split("-"))
        return f"{vendor.capitalize()}_{rest}"
    return None


def from_templates(
    page_type: str, source_roots: list[Path], index: SourceIndex | None = None
) -> EntryPoints:
    """Collect entry points statically, by following layout handles to their templates."""
    handle = PAGE_TYPES.get(page_type)
    if handle is None:
        raise EntryPointError(f"unknown page type: {page_type}")
    index = index if index is not None else SourceIndex(source_roots)
    found = EntryPoints(page_type=page_type, source="static")
    handles = [*BASE_HANDLES, handle]
    for layout in index.layouts_for(handles):
        for component in components_in_layout(layout):
            found.add(component, str(layout))
        for reference in templates_in_layout(layout):
            template = index.resolve_template(reference)
            if template is None:
                continue
            try:
                text = template.read_text("utf-8", errors="replace")
            except OSError:
                continue
            for match in INIT_BLOCK.finditer(text):
                for name in re.findall(COMPONENT_KEY, match.group(1)):
                    found.add(name, str(template))
            for match in re.finditer(r"data-mage-init=['\"]?\{(.*?)\}", text, re.DOTALL):
                for name in re.findall(r"[\"']([\w][\w./-]*)[\"']\s*:", match.group(1)):
                    found.add(name, str(template))
    return found
