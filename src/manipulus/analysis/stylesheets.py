"""Reports what CSS a theme deploys, and how much of it a page could possibly use."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# A rule block: everything up to the opening brace is the selector list.
RULE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}", re.S)
AT_RULE = re.compile(r"@(?:media|supports|layer|container)[^{]*\{", re.I)
CLASS_TOKEN = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")
CLASS_ATTR = re.compile(r"""class\s*=\s*["']([^"']+)["']""", re.I)
COMMENT = re.compile(r"/\*.*?\*/", re.S)


@dataclass
class Stylesheet:
    """One deployed CSS file and what it contains."""

    path: Path
    relative: str
    bytes_on_disk: int
    rule_count: int
    classes: set[str] = field(default_factory=set)

    @property
    def kilobytes(self) -> float:
        return self.bytes_on_disk / 1024


@dataclass
class Coverage:
    """How much of a stylesheet a given page could use, judged by class names alone."""

    stylesheet: str
    classes_in_css: int
    classes_present: int

    @property
    def percent(self) -> float:
        if not self.classes_in_css:
            return 100.0
        return 100.0 * self.classes_present / self.classes_in_css


def classes_in(css: str) -> set[str]:
    return set(CLASS_TOKEN.findall(css))


def count_rules(css: str) -> int:
    """Count style rules, ignoring at-rule wrappers and comments."""
    stripped = COMMENT.sub("", css)
    stripped = AT_RULE.sub("", stripped)
    return sum(1 for match in RULE.finditer(stripped) if match.group("body").strip())


def read_theme(theme_root: Path) -> list[Stylesheet]:
    """Every stylesheet deployed under a theme and locale."""
    sheets = []
    for file in sorted(theme_root.rglob("*.css")):
        if not file.is_file():
            continue
        try:
            text = file.read_text("utf-8", errors="replace")
        except OSError:
            continue
        sheets.append(
            Stylesheet(
                path=file,
                relative=file.relative_to(theme_root).as_posix(),
                bytes_on_disk=file.stat().st_size,
                rule_count=count_rules(text),
                classes=classes_in(text),
            )
        )
    return sheets


def classes_on_page(html: str) -> set[str]:
    found: set[str] = set()
    for value in CLASS_ATTR.findall(html):
        found.update(value.split())
    return found


def linked_stylesheets(html: str) -> list[str]:
    return re.findall(r"""<link[^>]+href=["']([^"']+\.css[^"']*)["']""", html, re.I)


def coverage(sheets: list[Stylesheet], html: str) -> list[Coverage]:
    """Estimate usage by asking which of a stylesheet's class names appear in the markup.

    This is a floor, not a verdict. It cannot see a class JavaScript adds after load, and
    it ignores element and attribute selectors entirely, so a low number is a candidate
    for review rather than a licence to delete.
    """
    present = classes_on_page(html)
    out = []
    for sheet in sheets:
        if not sheet.classes:
            continue
        out.append(
            Coverage(
                stylesheet=sheet.relative,
                classes_in_css=len(sheet.classes),
                classes_present=len(sheet.classes & present),
            )
        )
    return out
