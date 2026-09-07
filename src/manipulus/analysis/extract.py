"""Pulls dependency names out of one JavaScript file, fast enough to run over a whole theme."""

from __future__ import annotations

from pathlib import Path

import tree_sitter_javascript as tsjs
from tree_sitter import Language, Parser, Query, QueryCursor

from .jsparse import unquote

DEFINE_CALLS = {"define"}
REQUIRE_CALLS = {"require", "requirejs", "require.async"}
DEPENDENCY_CALLS = DEFINE_CALLS | REQUIRE_CALLS

# Matching call expressions in the query keeps the node walk in C rather than Python,
# which is roughly three times faster over a full theme.
CALL_QUERY = """
(call_expression
  function: [(identifier) (member_expression)] @callee
  arguments: (arguments) @args) @call
"""

_LANGUAGE: Language | None = None
_PARSER: Parser | None = None
_QUERY: Query | None = None


def _ensure_parser() -> tuple[Parser, Query]:
    """Build the parser once per process; neither object can be pickled to a worker."""
    global _LANGUAGE, _PARSER, _QUERY
    if _PARSER is None or _QUERY is None:
        _LANGUAGE = Language(tsjs.language())
        _PARSER = Parser(_LANGUAGE)
        _QUERY = Query(_LANGUAGE, CALL_QUERY)
    return _PARSER, _QUERY


def dependency_names(source: bytes) -> tuple[list[str], list[str]]:
    """Return the literal dependency names in this file, and any that are computed at runtime."""
    parser, query = _ensure_parser()
    tree = parser.parse(source)
    captures = QueryCursor(query).captures(tree.root_node)

    names: list[str] = []
    unresolved: list[str] = []

    for call in captures.get("call", []):
        callee = call.child_by_field_name("function")
        arguments = call.child_by_field_name("arguments")
        if callee is None or arguments is None:
            continue
        callee_text = source[callee.start_byte : callee.end_byte].decode("utf8", "replace")
        if callee_text not in DEPENDENCY_CALLS:
            continue

        positional = [c for c in arguments.named_children if c.type != "comment"]
        if not positional:
            continue
        target = positional[0]
        if target.type == "string":
            if callee_text in DEFINE_CALLS:
                # A named define is define('id', [deps], factory); the list is second.
                target = positional[1] if len(positional) > 1 else None
                if target is None:
                    continue
            else:
                # CommonJS sugar: define(function (require) { require('./dep') }). Four
                # files in a stock Luma tree use this, and between them they pull in two
                # dozen modules the array form never mentions.
                raw = source[target.start_byte : target.end_byte].decode("utf8", "replace")
                names.append(unquote(raw))
                continue
        if target.type != "array":
            if target.type in ("identifier", "member_expression", "binary_expression"):
                raw = source[target.start_byte : target.end_byte].decode("utf8", "replace")
                unresolved.append(raw[:80])
            continue

        for element in target.named_children:
            if element.type == "comment":
                continue
            raw = source[element.start_byte : element.end_byte].decode("utf8", "replace")
            if element.type == "string":
                names.append(unquote(raw))
            else:
                unresolved.append(raw[:80])

    return names, unresolved


def scan_file(job: tuple[str, str]) -> tuple[str, list[str], list[str], str | None]:
    """Read and scan one file. Returns its module id, names, unresolved names and any error."""
    module_id, path = job
    try:
        source = Path(path).read_bytes()
    except OSError as error:
        return module_id, [], [], f"could not read {path}: {error}"
    try:
        names, unresolved = dependency_names(source)
    except Exception as error:  # noqa: BLE001 - the file is reported, never skipped silently
        return module_id, [], [], f"could not parse {path}: {error}"
    return module_id, names, unresolved, None
