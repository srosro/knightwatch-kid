"""Ollama embedding client.

Model and endpoint are configurable via environment variables so each host can
point at its own Ollama and pick a model that fits its hardware:

- ``KID_EMBED_MODEL``     embedding model (default ``mxbai-embed-large``)
- ``KID_OLLAMA_URL``      Ollama base URL (default ``http://localhost:11434``)
- ``KID_MAX_EMBED_CHARS`` per-element input truncation (default ``900``)

The vector dimension is inferred from the model at index time, so switching
``KID_EMBED_MODEL`` to a model with a different dimension requires re-indexing.
"""

from __future__ import annotations

import os

import requests

from keepitdry.parser import CodeElement

OLLAMA_BASE_URL = os.environ.get("KID_OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("KID_EMBED_MODEL", "mxbai-embed-large")
# Truncate per-element input to the model's context. Dense code tokenizes near
# 1.7 chars/token; the 900 default suits mxbai-embed-large's 512-token context.
# Raise it (e.g. KID_MAX_EMBED_CHARS) for longer-context models like qwen3.
_MAX_EMBED_CHARS = int(os.environ.get("KID_MAX_EMBED_CHARS", "900"))


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
    text = "\n".join(parts)
    if len(text) > _MAX_EMBED_CHARS:
        text = text[:_MAX_EMBED_CHARS]
    return text


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


_BATCH_SIZE = 10


def batch_embed(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts in batched API calls."""
    all_embeddings = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": MODEL, "input": batch},
            timeout=60,
        )
        resp.raise_for_status()
        all_embeddings.extend(resp.json()["embeddings"])
    return all_embeddings
