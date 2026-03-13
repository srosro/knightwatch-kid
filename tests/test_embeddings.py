from unittest.mock import patch, Mock

import pytest
import requests as req

from keepitdry.embeddings import (
    build_searchable_text,
    embed,
    batch_embed,
    check_ollama,
    OllamaError,
)
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


def _mock_embed_response(texts=None, dim=1024):
    """Create a mock response for Ollama /api/embed endpoint."""
    count = len(texts) if texts else 1
    resp = Mock()
    resp.status_code = 200
    resp.json.return_value = {"embeddings": [[0.1] * dim for _ in range(count)]}
    resp.raise_for_status = Mock()
    return resp


def test_check_ollama_success():
    with patch("keepitdry.embeddings.requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=200)
        check_ollama()


def test_check_ollama_failure():
    with patch("keepitdry.embeddings.requests.get") as mock_get:
        mock_get.side_effect = req.ConnectionError("refused")
        with pytest.raises(OllamaError, match="Ollama"):
            check_ollama()


def test_embed_single():
    with patch("keepitdry.embeddings.requests.post") as mock_post:
        mock_post.return_value = _mock_embed_response(["hello world"])

        vec = embed("hello world")

        assert len(vec) == 1024
        assert all(isinstance(v, float) for v in vec)
        mock_post.assert_called_once()


def test_batch_embed():
    texts = ["text one", "text two", "text three"]
    with patch("keepitdry.embeddings.requests.post") as mock_post:
        mock_post.return_value = _mock_embed_response(texts)

        vecs = batch_embed(texts)

        assert len(vecs) == 3
        assert all(len(v) == 1024 for v in vecs)
        mock_post.assert_called_once()
