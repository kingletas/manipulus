"""What a --url is for: evidence on top of the templates, or the whole answer."""

from __future__ import annotations

from argparse import Namespace

import pytest

from manipulus import cli
from manipulus.analysis import entrypoints


class _Found:
    def __init__(self, names):
        self.names = set(names)


@pytest.fixture
def stubbed(monkeypatch):
    """Templates and a rendered page that disagree, which is the case that matters."""
    monkeypatch.setattr(entrypoints, "PAGE_TYPES", ["category", "checkout"])
    monkeypatch.setattr(entrypoints, "SourceIndex", lambda roots: None)
    monkeypatch.setattr(
        entrypoints, "from_templates", lambda page, roots, index=None: _Found({"from_layout"})
    )
    monkeypatch.setattr(entrypoints, "fetch", lambda url, timeout=None: "<html></html>")
    monkeypatch.setattr(
        entrypoints, "from_html", lambda html, page, url: _Found({"from_page"})
    )


def _args(mode, tmp_path):
    return Namespace(
        root=str(tmp_path),
        url=["category=http://store.test/c.html"],
        url_entries=mode,
        timeout=1.0,
    )


def test_add_keeps_what_the_templates_found(stubbed, tmp_path):
    per_page, sources = cli.collect_entry_points(_args("add", tmp_path), None, None)

    assert per_page["category"] == {"from_layout", "from_page"}
    assert sources["category"] == "static+html"


def test_only_believes_the_page_over_the_layout(stubbed, tmp_path):
    per_page, sources = cli.collect_entry_points(_args("only", tmp_path), None, None)

    assert per_page["category"] == {"from_page"}
    assert sources["category"] == "html"


def test_a_page_type_with_no_url_is_untouched_either_way(stubbed, tmp_path):
    for mode in ("add", "only"):
        per_page, sources = cli.collect_entry_points(_args(mode, tmp_path), None, None)

        assert per_page["checkout"] == {"from_layout"}, mode
        assert sources["checkout"] == "static", mode


def test_the_default_is_the_safe_one(stubbed, tmp_path):
    """`only` is smaller and blind to anything that page did not render."""
    args = _args("add", tmp_path)
    del args.url_entries

    per_page, _ = cli.collect_entry_points(args, None, None)

    assert per_page["category"] == {"from_layout", "from_page"}
