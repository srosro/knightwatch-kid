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


class OllamaError(Exception):
    """Raised when Ollama is unreachable or returns an error."""


def check_ollama() -> None:
    """Verify Ollama server is running and reachable."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
    except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
        raise OllamaError(
            f"Ollama is not reachable at {OLLAMA_BASE_URL}. "
            "Make sure Ollama is running: https://ollama.ai"
        ) from e


def embed(text: str) -> list[float]:
    """Generate embedding for a single text."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": MODEL, "input": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"][0]


def batch_embed(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts. Single API call."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": MODEL, "input": texts},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]
