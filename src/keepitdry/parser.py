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


def _extract_class_signature(node) -> str:
    """Extract the class signature line (e.g. 'class Name(Base)')."""
    text = node.text.decode("utf8")
    first_line = text.split("\n")[0]
    if first_line.rstrip().endswith(":"):
        return first_line.rstrip()[:-1].strip()
    return first_line.strip()


def _extract_classes(root, file_path: str, parent_chain: str) -> list[CodeElement]:
    """Extract class definitions and their methods from direct children of root."""
    elements = []
    for child in root.children:
        node = child
        # Unwrap decorated definitions
        if node.type == "decorated_definition":
            for sub in node.children:
                if sub.type == "class_definition":
                    node = sub
                    break
            else:
                continue

        if node.type != "class_definition":
            continue

        name_node = node.child_by_field_name("name")
        if not name_node:
            continue

        class_name = name_node.text.decode("utf8")
        body = node.child_by_field_name("body")

        elements.append(
            CodeElement(
                file_path=file_path,
                element_name=class_name,
                element_type="class",
                signature=_extract_class_signature(node),
                docstring=_extract_docstring(body),
                code_body=node.text.decode("utf8"),
                line_number=node.start_point[0] + 1,
                parent_chain=parent_chain,
            )
        )

        # Extract methods from the class body
        if body:
            method_parent = f"{parent_chain} > {class_name}"
            for body_child in body.children:
                method_node = body_child
                if method_node.type == "decorated_definition":
                    for sub in method_node.children:
                        if sub.type == "function_definition":
                            method_node = sub
                            break
                    else:
                        continue

                if method_node.type != "function_definition":
                    continue

                method_name_node = method_node.child_by_field_name("name")
                if not method_name_node:
                    continue

                method_name = method_name_node.text.decode("utf8")
                method_body = method_node.child_by_field_name("body")

                elements.append(
                    CodeElement(
                        file_path=file_path,
                        element_name=f"{class_name}.{method_name}",
                        element_type="method",
                        signature=_extract_signature(method_node),
                        docstring=_extract_docstring(method_body),
                        code_body=method_node.text.decode("utf8"),
                        line_number=method_node.start_point[0] + 1,
                        parent_chain=method_parent,
                    )
                )

    return elements


def _extract_variables(root, file_path: str, parent_chain: str) -> list[CodeElement]:
    """Extract module-level variable assignments from direct children."""
    elements = []
    for child in root.children:
        if child.type == "expression_statement":
            for sub in child.children:
                if sub.type == "assignment":
                    _extract_assignment(sub, file_path, parent_chain, elements)

    return elements


def _extract_assignment(node, file_path: str, parent_chain: str, elements: list):
    """Extract a single assignment as a variable CodeElement."""
    left = node.child_by_field_name("left")
    if not left:
        return

    # Only extract simple name assignments (not tuple unpacking, subscripts, etc.)
    if left.type != "identifier":
        return

    name = left.text.decode("utf8")

    elements.append(CodeElement(
        file_path=file_path,
        element_name=name,
        element_type="variable",
        signature=node.text.decode("utf8").split("\n")[0].strip(),
        docstring=None,
        code_body=node.text.decode("utf8"),
        line_number=node.start_point[0] + 1,
        parent_chain=parent_chain,
    ))


def parse_file(path: Path, project_root: Path) -> list[CodeElement]:
    """Parse a Python file and extract code elements."""
    source = path.read_bytes()
    tree = _parser.parse(source)
    root = tree.root_node

    rel_path = str(path.relative_to(project_root))
    parent_chain = rel_path

    elements = []
    elements.extend(_extract_variables(root, rel_path, parent_chain))
    elements.extend(_extract_functions(root, rel_path, parent_chain))
    elements.extend(_extract_classes(root, rel_path, parent_chain))

    return elements
