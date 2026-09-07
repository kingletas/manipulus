"""Reads JavaScript with tree-sitter and turns literal syntax into Python values."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import tree_sitter_javascript as tsjs
from tree_sitter import Language, Node, Parser

_LANGUAGE = Language(tsjs.language())
_PARSER = Parser(_LANGUAGE)

SCOPE_TYPES = ("function_expression", "function_declaration", "arrow_function", "program")


class Unresolvable:
    """A value the source computes at runtime, so no literal exists to read."""

    __slots__ = ("source",)

    def __init__(self, source: str) -> None:
        self.source = source

    def __repr__(self) -> str:
        return f"Unresolvable({self.source[:40]!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Unresolvable) and other.source == self.source

    def __hash__(self) -> int:
        return hash(("Unresolvable", self.source))


def parse(source: bytes) -> Node:
    return _PARSER.parse(source).root_node


def walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.children:
        yield from walk(child)


def text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf8", "replace")


def unquote(raw: str) -> str:
    if len(raw) >= 2 and raw[0] in "'\"`" and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


def literal(node: Node, source: bytes) -> Any:
    """Convert a literal node into the Python value it denotes, or Unresolvable."""
    kind = node.type
    if kind in ("string", "template_string"):
        return unquote(text(node, source))
    if kind == "number":
        raw = text(node, source)
        try:
            return float(raw) if ("." in raw or "e" in raw.lower()) else int(raw, 0)
        except ValueError:
            return Unresolvable(raw)
    if kind == "true":
        return True
    if kind == "false":
        return False
    if kind in ("null", "undefined"):
        return None
    if kind == "array":
        return [literal(c, source) for c in node.named_children if c.type != "comment"]
    if kind == "object":
        out: dict[str, Any] = {}
        for pair in node.named_children:
            if pair.type != "pair":
                continue
            key_node = pair.child_by_field_name("key")
            value_node = pair.child_by_field_name("value")
            if key_node is None or value_node is None:
                continue
            out[unquote(text(key_node, source))] = literal(value_node, source)
        return out
    return Unresolvable(text(node, source))


def enclosing_scope(node: Node) -> Node | None:
    current = node.parent
    while current is not None and current.type not in SCOPE_TYPES:
        current = current.parent
    return current


def declared_object(scope: Node, name: str, source: bytes) -> Node | None:
    """Find the last `var <name> = {...}` inside this scope."""
    found = None
    for node in walk(scope):
        if node.type != "variable_declarator":
            continue
        ident = node.child_by_field_name("name")
        value = node.child_by_field_name("value")
        if ident is None or value is None or value.type != "object":
            continue
        if text(ident, source) == name:
            found = value
    return found


def resolve_object_argument(call: Node, source: bytes) -> Node | None:
    """Return the object literal a call was given, following one identifier if needed."""
    arguments = call.child_by_field_name("arguments")
    if arguments is None:
        return None
    argument = next((c for c in arguments.named_children if c.type != "comment"), None)
    if argument is None:
        return None
    if argument.type == "object":
        return argument
    if argument.type != "identifier":
        return None
    name = text(argument, source)
    scope = enclosing_scope(call)
    while scope is not None:
        target = declared_object(scope, name, source)
        if target is not None:
            return target
        scope = enclosing_scope(scope)
    return None


def calls_named(root: Node, source: bytes, names: set[str]) -> Iterator[Node]:
    """Yield every call expression whose callee text matches one of the given names."""
    for node in walk(root):
        if node.type != "call_expression":
            continue
        callee = node.child_by_field_name("function")
        if callee is not None and text(callee, source) in names:
            yield node
