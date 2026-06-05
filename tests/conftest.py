import pytest
from pathlib import Path


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with sample Python files."""
    src = tmp_path / "example.py"
    src.write_text(
        'def greet(name: str) -> str:\n'
        '    """Say hello."""\n'
        '    return f"Hello, {name}"\n'
        '\n'
        '\n'
        'class Calculator:\n'
        '    """A simple calculator."""\n'
        '\n'
        '    def add(self, a: int, b: int) -> int:\n'
        '        return a + b\n'
        '\n'
        '    def subtract(self, a: int, b: int) -> int:\n'
        '        return a - b\n'
        '\n'
        '\n'
        'MAX_RETRIES = 3\n'
    )
    return tmp_path


@pytest.fixture
def fake_embed():
    """Return a function that produces deterministic fake embeddings."""
    def _embed(text: str) -> list[float]:
        # Deterministic: hash-based, EMBEDDING_DIM floats
        import hashlib
        from keepitdry.embeddings import EMBEDDING_DIM
        h = hashlib.sha256(text.encode()).digest()
        # Repeat the 32-byte digest enough times to cover EMBEDDING_DIM
        raw = (h * (EMBEDDING_DIM // len(h) + 1))[:EMBEDDING_DIM]
        return [float(b) / 255.0 for b in raw]
    return _embed
