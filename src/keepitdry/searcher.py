"""Query embedding + search + ranking."""

from __future__ import annotations

from pathlib import Path

from keepitdry import embeddings as embed_module
from keepitdry.store import Store


class Searcher:
    def __init__(self, project_root: Path):
        self.root = project_root
        self.store = Store(project_root / ".keepitdry")

    def search(
        self,
        query: str,
        limit: int = 5,
        element_type: str | None = None,
        file_path: str | None = None,
    ) -> list[dict]:
        if self.store.count() == 0:
            return []

        query_vec = embed_module.embed(query)

        where = {}
        if element_type:
            where["element_type"] = element_type
        if file_path:
            where["file_path"] = file_path

        raw = self.store.search(
            query_embedding=query_vec,
            limit=limit,
            where=where if where else None,
        )

        results = []
        for item in raw:
            meta = item["metadata"]
            results.append({
                "file_path": meta.get("file_path", ""),
                "element_name": meta.get("element_name", ""),
                "element_type": meta.get("element_type", ""),
                "line_number": meta.get("line_number", 0),
                "signature": meta.get("signature", ""),
                "parent_chain": meta.get("parent_chain", ""),
                "code": item.get("document", ""),
                "similarity": max(0.0, 1.0 - item["distance"]) if item["distance"] is not None else 0.0,
            })

        return results
