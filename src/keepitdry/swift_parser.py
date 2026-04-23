"""Tree-sitter Swift code extraction."""

from __future__ import annotations

from pathlib import Path

import tree_sitter_swift as tss
from tree_sitter import Language, Parser

from keepitdry.parser import CodeElement

SWIFT_LANGUAGE = Language(tss.language())
_parser = Parser(SWIFT_LANGUAGE)

_TYPE_KEYWORDS = ("class", "struct", "enum", "protocol", "actor", "extension")


def _get_name(node) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node:
        return name_node.text.decode("utf8")
    for c in node.children:
        if c.type == "type_identifier":
            return c.text.decode("utf8")
        if c.type == "user_type":
            return c.text.decode("utf8")
    return None


def _get_kind_keyword(node) -> str:
    for c in node.children:
        if c.type in _TYPE_KEYWORDS:
            return c.type
    return "type"


def _signature(node) -> str:
    text = node.text.decode("utf8")
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.endswith("{"):
            stripped = stripped[:-1].rstrip()
        return stripped
    return ""


def _leading_doc_comment(node) -> str | None:
    """Walk backwards through prev_sibling, collecting /// doc comment lines."""
    prev = node.prev_sibling
    lines: list[str] = []
    while prev is not None and prev.type == "comment":
        text = prev.text.decode("utf8", errors="replace")
        if text.startswith("///"):
            lines.insert(0, text[3:].strip())
        else:
            break
        prev = prev.prev_sibling
    return "\n".join(lines) if lines else None


def _body_node(node):
    for c in node.children:
        if c.type in ("class_body", "enum_class_body", "protocol_body"):
            return c
    return None


def _iter_body_decls(body_node):
    for child in body_node.children:
        if child.type in (
            "function_declaration",
            "property_declaration",
            "init_declaration",
            "deinit_declaration",
            "class_declaration",
            "protocol_function_declaration",
            "protocol_property_declaration",
            "enum_entry",
        ):
            yield child


def _property_is_computed(node) -> bool:
    """A property_declaration is computed if it has a body with explicit get/set."""
    text = node.text.decode("utf8", errors="replace")
    # A stored property never has braces inside the declaration; computed always does.
    # Trivial heuristic: presence of a brace-block on the same declaration.
    return "{" in text and "}" in text


def parse_swift_file(path: Path, project_root: Path) -> list[CodeElement]:
    """Parse a Swift file and extract code elements."""
    source = path.read_bytes()
    tree = _parser.parse(source)
    root = tree.root_node

    rel_path = str(path.relative_to(project_root))
    parent_chain = rel_path

    elements: list[CodeElement] = []

    for child in root.children:
        if child.type == "function_declaration":
            _emit_function(child, elements, rel_path, parent_chain, element_type="function")
        elif child.type == "property_declaration":
            _emit_property(child, elements, rel_path, parent_chain, owner_name=None)
        elif child.type in ("class_declaration", "protocol_declaration"):
            _emit_type(child, elements, rel_path, parent_chain)

    return elements


def _emit_function(node, elements, rel_path, parent_chain, element_type, owner_name=None):
    name = _get_name(node)
    if not name:
        return
    display = f"{owner_name}.{name}" if owner_name else name
    elements.append(
        CodeElement(
            file_path=rel_path,
            element_name=display,
            element_type=element_type,
            signature=_signature(node),
            docstring=_leading_doc_comment(node),
            code_body=node.text.decode("utf8", errors="replace"),
            line_number=node.start_point[0] + 1,
            parent_chain=parent_chain,
        )
    )


def _emit_init(node, elements, rel_path, parent_chain, owner_name):
    display = f"{owner_name}.init"
    elements.append(
        CodeElement(
            file_path=rel_path,
            element_name=display,
            element_type="method",
            signature=_signature(node),
            docstring=_leading_doc_comment(node),
            code_body=node.text.decode("utf8", errors="replace"),
            line_number=node.start_point[0] + 1,
            parent_chain=parent_chain,
        )
    )


def _emit_property(node, elements, rel_path, parent_chain, owner_name):
    name = _get_name(node)
    if not name:
        return
    display = f"{owner_name}.{name}" if owner_name else name
    # Computed properties act like methods for DRY purposes — their body may contain
    # switch statements / derivations that are the interesting thing to dedupe.
    kind = "method" if owner_name and _property_is_computed(node) else "variable"
    elements.append(
        CodeElement(
            file_path=rel_path,
            element_name=display,
            element_type=kind,
            signature=_signature(node),
            docstring=_leading_doc_comment(node),
            code_body=node.text.decode("utf8", errors="replace"),
            line_number=node.start_point[0] + 1,
            parent_chain=parent_chain,
        )
    )


def _emit_type(node, elements, rel_path, parent_chain):
    keyword = _get_kind_keyword(node)
    raw_name = _get_name(node)
    if not raw_name:
        return

    display_name = f"extension {raw_name}" if keyword == "extension" else raw_name

    elements.append(
        CodeElement(
            file_path=rel_path,
            element_name=display_name,
            element_type="class",
            signature=_signature(node),
            docstring=_leading_doc_comment(node),
            code_body=node.text.decode("utf8", errors="replace"),
            line_number=node.start_point[0] + 1,
            parent_chain=parent_chain,
        )
    )

    body = _body_node(node)
    if not body:
        return

    nested_chain = f"{parent_chain} > {display_name}"

    for member in _iter_body_decls(body):
        if member.type in ("function_declaration", "protocol_function_declaration"):
            _emit_function(
                member, elements, rel_path, nested_chain,
                element_type="method", owner_name=display_name,
            )
        elif member.type in ("init_declaration", "deinit_declaration"):
            _emit_init(member, elements, rel_path, nested_chain, owner_name=display_name)
        elif member.type in ("property_declaration", "protocol_property_declaration"):
            _emit_property(member, elements, rel_path, nested_chain, owner_name=display_name)
        elif member.type in ("class_declaration", "protocol_declaration"):
            # Nested type
            _emit_type(member, elements, rel_path, nested_chain)
