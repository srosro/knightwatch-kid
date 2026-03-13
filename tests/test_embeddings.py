from unittest.mock import patch, Mock

import pytest
import requests as req

from keepitdry.embeddings import build_searchable_text
from keepitdry.parser import CodeElement


def test_build_searchable_text_full():
    el = CodeElement(
        file_path="utils.py",
        element_name="parse_config",
        element_type="function",
        signature="def parse_config(path: str) -> dict",
        docstring="Parse a YAML config file.",
        code_body="def parse_config(path: str) -> dict:\n    ...",
        line_number=1,
        parent_chain="utils.py",
    )

    text = build_searchable_text(el)

    assert "utils.py" in text
    assert "parse_config" in text
    assert "def parse_config(path: str) -> dict" in text
    assert "Parse a YAML config file." in text
    assert "def parse_config(path: str) -> dict:\n    ..." in text


def test_build_searchable_text_no_docstring():
    el = CodeElement(
        file_path="f.py",
        element_name="add",
        element_type="function",
        signature="def add(a, b)",
        docstring=None,
        code_body="def add(a, b):\n    return a + b",
        line_number=1,
        parent_chain="f.py",
    )

    text = build_searchable_text(el)

    assert "add" in text
    assert "def add(a, b)" in text
    assert "None" not in text
