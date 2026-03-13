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
        # Deterministic: hash-based, 1024-dim
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        # Extend to 1024 floats by repeating hash
        raw = (h * 32)[:1024]
        return [float(b) / 255.0 for b in raw]
    return _embed
