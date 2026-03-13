"""Orchestrates the index pipeline: parse -> embed -> store."""

from __future__ import annotations

import hashlib
import json
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


class FileHashTracker:
    """Track file content hashes for incremental indexing."""

    def __init__(self, path: Path):
        self._path = path
        self._hashes: dict[str, str] = {}
        if path.exists():
            self._hashes = json.loads(path.read_text())

    def _compute_hash(self, file_path: Path) -> str:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()

    def has_changed(self, file_path: Path) -> bool:
        current = self._compute_hash(file_path)
        return self._hashes.get(str(file_path)) != current

    def update(self, file_path: Path) -> None:
        self._hashes[str(file_path)] = self._compute_hash(file_path)

    def remove(self, file_path: str) -> None:
        self._hashes.pop(file_path, None)

    def stale_files(self, current_files: set[str]) -> list[str]:
        return [f for f in self._hashes if f not in current_files]

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._hashes))
