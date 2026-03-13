"""ChromaDB per-project vector store."""

from __future__ import annotations

from pathlib import Path

import chromadb


COLLECTION_NAME = "keepitdry"


class Store:
    """Manages a ChromaDB collection for a single project."""

    def __init__(self, db_path: Path):
        self._client = chromadb.PersistentClient(path=str(db_path))
        self.collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        documents: list[str],
    ) -> None:
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def delete(self, ids: list[str]) -> None:
        self.collection.delete(ids=ids)

    def count(self) -> int:
        return self.collection.count()

    def clear(self) -> None:
        self._client.delete_collection(COLLECTION_NAME)
        self.collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
