"""Orchestrates the index pipeline: parse -> embed -> store."""

from __future__ import annotations

from pathlib import Path

SKIP_DIRS = frozenset({
    ".keepitdry", "__pycache__", "node_modules", ".venv",
    ".git", ".tox", ".mypy_cache", ".pytest_cache",
})


def discover_python_files(root: Path) -> list[Path]:
    """Find all .py files under root, skipping excluded directories."""
    files = []
    for path in sorted(root.rglob("*.py")):
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        files.append(path)
    return files
