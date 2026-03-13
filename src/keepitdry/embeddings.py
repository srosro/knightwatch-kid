"""Ollama embedding client for mxbai-embed-large."""

from __future__ import annotations

import requests

from keepitdry.parser import CodeElement

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL = "mxbai-embed-large"
EMBEDDING_DIM = 1024


def build_searchable_text(element: CodeElement) -> str:
    """Construct the text to embed for a code element."""
    parts = [
        element.parent_chain,
        element.element_name,
        element.signature,
    ]
    if element.docstring:
        parts.append(element.docstring)
    parts.append(element.code_body)
    return "\n".join(parts)
