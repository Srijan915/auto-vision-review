"""Persistent local FAISS vector storage with source metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Sequence

import faiss
import numpy as np


@dataclass(frozen=True)
class StoredChunk:
    chunk_id: str
    document_id: str
    source_path: str
    source_sha256: str
    chunk_index: int
    text: str
    metadata: dict[str, Any]


class FaissVectorStore:
    """Cosine-similarity index persisted as FAISS bytes plus JSON metadata."""

    def __init__(self, directory: str | Path, dimension: int) -> None:
        self.directory = Path(directory)
        self.dimension = dimension
        self.index_path = self.directory / "chunks.faiss"
        self.metadata_path = self.directory / "chunks.json"
        self.index = faiss.IndexFlatIP(dimension)
        self.chunks: list[StoredChunk] = []

    def add(self, chunks: Sequence[StoredChunk], embeddings: np.ndarray) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Chunk and embedding counts must match")
        if embeddings.ndim != 2 or embeddings.shape[1] != self.dimension:
            raise ValueError("Embedding dimension does not match this store")
        if not len(chunks):
            return
        self.index.add(np.asarray(embeddings, dtype=np.float32))
        self.chunks.extend(chunks)

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> list[tuple[StoredChunk, float]]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        if not self.chunks:
            return []
        query = np.asarray(query_embedding, dtype=np.float32).reshape(1, -1)
        if query.shape[1] != self.dimension:
            raise ValueError("Query embedding dimension does not match this store")
        scores, indexes = self.index.search(query, min(top_k, len(self.chunks)))
        return [(self.chunks[int(index)], float(score)) for score, index in zip(scores[0], indexes[0]) if index >= 0]

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        self.metadata_path.write_text(json.dumps({"dimension": self.dimension, "chunks": [asdict(chunk) for chunk in self.chunks]}, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, directory: str | Path) -> "FaissVectorStore":
        directory = Path(directory)
        metadata = json.loads((directory / "chunks.json").read_text(encoding="utf-8"))
        store = cls(directory, int(metadata["dimension"]))
        store.index = faiss.read_index(str(directory / "chunks.faiss"))
        store.chunks = [StoredChunk(**chunk) for chunk in metadata["chunks"]]
        if store.index.ntotal != len(store.chunks):
            raise ValueError("FAISS index and chunk metadata have inconsistent lengths")
        return store
