"""Orchestrates the index pipeline: parse -> embed -> store."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from keepitdry import embeddings as embed_module
from keepitdry.parser import parse_file, chunk_elements
from keepitdry.store import Store

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


class Indexer:
    """Orchestrates parse -> embed -> store for a project."""

    def __init__(self, project_root: Path):
        self.root = project_root
        self.db_path = project_root / ".keepitdry"
        self.store = Store(self.db_path)
        self._tracker = FileHashTracker(self.db_path / "file_hashes.json")

    def index(self, clear: bool = False) -> dict:
        if clear:
            self.clear()

        py_files = discover_python_files(self.root)
        current_paths = {str(f) for f in py_files}

        # Remove stale entries
        stale = self._tracker.stale_files(current_paths)
        for stale_path in stale:
            rel = str(Path(stale_path).relative_to(self.root))
            self.store.delete_by_file(rel)
            self._tracker.remove(stale_path)

        files_indexed = 0
        files_skipped = 0
        total_elements = 0

        for py_file in py_files:
            if not self._tracker.has_changed(py_file):
                files_skipped += 1
                continue

            elements = parse_file(py_file, project_root=self.root)
            elements = chunk_elements(elements)

            if not elements:
                self._tracker.update(py_file)
                continue

            rel_path = str(py_file.relative_to(self.root))
            self.store.delete_by_file(rel_path)

            texts = [embed_module.build_searchable_text(el) for el in elements]
            embeddings = embed_module.batch_embed(texts)

            ids = [f"{el.file_path}::{el.element_name}::{el.line_number}" for el in elements]
            metadatas = [
                {
                    "file_path": el.file_path,
                    "element_type": el.element_type,
                    "element_name": el.element_name,
                    "line_number": el.line_number,
                    "parent_chain": el.parent_chain,
                    "signature": el.signature,
                }
                for el in elements
            ]
            documents = [el.code_body for el in elements]

            self.store.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents,
            )

            self._tracker.update(py_file)
            files_indexed += 1
            total_elements += len(elements)

        self._tracker.save()

        return {
            "files_indexed": files_indexed,
            "files_skipped": files_skipped,
            "elements_indexed": total_elements,
            "stale_removed": len(stale),
        }

    def clear(self) -> None:
        self.store.clear()
        self._tracker = FileHashTracker(self.db_path / "file_hashes.json")
        if (self.db_path / "file_hashes.json").exists():
            (self.db_path / "file_hashes.json").unlink()

    def stats(self) -> dict:
        return {
            "total_elements": self.store.count(),
            "db_path": str(self.db_path),
        }
