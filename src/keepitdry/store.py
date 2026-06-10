"""ChromaDB per-project vector store."""

from __future__ import annotations

from pathlib import Path

import chromadb

from keepitdry.embeddings import EMBEDDING_DIM


COLLECTION_NAME = "keepitdry"


def _collection_metadata() -> dict:
    # Stamp the embedding dimension so a model swap can detect and rebuild a
    # collection persisted with vectors of a different dimension, rather than
    # crashing on the first upsert/query with a hard dimension mismatch.
    return {"hnsw:space": "cosine", "embedding_dim": EMBEDDING_DIM}


class Store:
    """Manages a ChromaDB collection for a single project."""

    def __init__(self, db_path: Path):
        self._client = chromadb.PersistentClient(path=str(db_path))
        self.collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata=_collection_metadata(),
        )
        # An on-disk collection from an earlier model has vectors of a different
        # dimension; rebuild it so the new model can index/query cleanly. Callers
        # that own state beyond the collection (e.g. the indexer's file-hash
        # tracker) must invalidate it too — see Indexer.__init__.
        self.rebuilt = self.collection.metadata.get("embedding_dim") != EMBEDDING_DIM
        if self.rebuilt:
            self.clear()

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

    def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        where: dict | None = None,
    ) -> list[dict]:
        """Search for similar elements. Returns list of result dicts."""
        n = self.count()
        if n == 0:
            return []

        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": min(limit, n),
        }
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        items = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                item = {
                    "id": id_,
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "document": results["documents"][0][i] if results["documents"] else "",
                }
                items.append(item)
        return items

    def delete_by_file(self, file_path: str) -> None:
        """Delete all elements belonging to a specific file."""
        self.collection.delete(where={"file_path": file_path})

    def clear(self) -> None:
        self._client.delete_collection(COLLECTION_NAME)
        self.collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata=_collection_metadata(),
        )
