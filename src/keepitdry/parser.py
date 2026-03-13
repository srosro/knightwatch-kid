"""Tree-sitter Python code extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())
_parser = Parser(PY_LANGUAGE)


@dataclass
class CodeElement:
    file_path: str
    element_name: str
    element_type: str  # "function" | "class" | "method" | "variable"
    signature: str
    docstring: str | None
    code_body: str
    line_number: int
    parent_chain: str


def _extract_docstring(body_node) -> str | None:
    """Extract docstring from the first statement in a body block."""
    if not body_node or body_node.child_count == 0:
        return None
    first = body_node.children[0]
    if first.type == "expression_statement" and first.child_count > 0:
        string_node = first.children[0]
        if string_node.type == "string":
            text = string_node.text.decode("utf8")
            for q in ('"""', "'''", '"', "'"):
                if text.startswith(q) and text.endswith(q):
                    return text[len(q) : -len(q)].strip()
    return None


def _extract_signature(node) -> str:
    """Extract the def line (everything up to the colon)."""
    text = node.text.decode("utf8")
    first_line = text.split("\n")[0]
    if first_line.rstrip().endswith(":"):
        return first_line.rstrip()[:-1].strip()
    return first_line.strip()


def _extract_functions(root, file_path: str, parent_chain: str) -> list[CodeElement]:
    """Extract function definitions from direct children of root."""
    elements = []
    for child in root.children:
        node = child
        # Unwrap decorated definitions
        if node.type == "decorated_definition":
            for sub in node.children:
                if sub.type == "function_definition":
                    node = sub
                    break
            else:
                continue

        if node.type != "function_definition":
            continue

        name_node = node.child_by_field_name("name")
        if not name_node:
            continue

        name = name_node.text.decode("utf8")
        body = node.child_by_field_name("body")

        elements.append(
            CodeElement(
                file_path=file_path,
                element_name=name,
                element_type="function",
                signature=_extract_signature(node),
                docstring=_extract_docstring(body),
                code_body=node.text.decode("utf8"),
                line_number=node.start_point[0] + 1,
                parent_chain=parent_chain,
            )
        )

    return elements


def parse_file(path: Path, project_root: Path) -> list[CodeElement]:
    """Parse a Python file and extract code elements."""
    source = path.read_bytes()
    tree = _parser.parse(source)
    root = tree.root_node

    rel_path = str(path.relative_to(project_root))
    parent_chain = rel_path

    elements = []
    elements.extend(_extract_functions(root, rel_path, parent_chain))

    return elements
