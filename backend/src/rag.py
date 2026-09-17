"""Informational retrieval for approved internal policy/process documents only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.embeddings import Embedder, SentenceTransformerEmbedder
from src.vector_store import FaissVectorStore, StoredChunk


SUPPORTED_DOCUMENT_SUFFIXES = frozenset({".txt", ".md", ".json"})
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RagSettings:
    """Runtime locations for an already-built, approved-document index."""

    documents_root: Path
    vector_store: Path
    embedding_model: str
    default_top_k: int = 5


def load_rag_settings(config_path: str | Path = PROJECT_ROOT / "configs" / "rag.yaml") -> RagSettings:
    """Load RAG settings without indexing documents or downloading a model."""
    path = Path(config_path).resolve()
    values = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError("RAG configuration must be a mapping")

    def project_path(value: str) -> Path:
        candidate = Path(value)
        return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate

    return RagSettings(
        documents_root=project_path(str(values["documents_root"])),
        vector_store=project_path(str(values["vector_store"])),
        embedding_model=str(values["embedding_model"]),
        default_top_k=int(values.get("default_top_k", 5)),
    )


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    document_id: str
    source_path: str
    score: float
    text: str
    metadata: dict[str, Any]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_document(path: Path) -> str:
    if path.suffix.lower() not in SUPPORTED_DOCUMENT_SUFFIXES:
        raise ValueError(f"Unsupported document type: {path.suffix}")
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        raw = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    return raw.strip()


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """Split text by words with deterministic overlap for source-citable chunks."""
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap smaller than chunk_size")
    words = text.split()
    return [" ".join(words[start : start + chunk_size]) for start in range(0, len(words), chunk_size - overlap) if words[start : start + chunk_size]]


def ingest_documents(documents_root: str | Path, embedder: Embedder, store_directory: str | Path, *, chunk_size: int = 300, overlap: int = 50) -> FaissVectorStore:
    """Build a new local retrieval store from approved documents under one root."""
    root = Path(documents_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Document root does not exist: {root}")
    chunks: list[StoredChunk] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.suffix.lower() not in SUPPORTED_DOCUMENT_SUFFIXES:
            continue
        text = _read_document(path)
        if not text:
            continue
        relative = path.relative_to(root).as_posix()
        source_sha256 = _file_sha256(path)
        document_id = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]
        for index, part in enumerate(chunk_text(text, chunk_size, overlap)):
            chunks.append(StoredChunk(
                chunk_id=f"{document_id}:{index}", document_id=document_id, source_path=relative,
                source_sha256=source_sha256, chunk_index=index, text=part,
                metadata={"document_type": path.suffix.lower().lstrip("."), "source_path": relative},
            ))
    if not chunks:
        raise ValueError("No supported non-empty documents were found for ingestion")
    store = FaissVectorStore(store_directory, embedder.dimension)
    if store.index_path.exists() or store.metadata_path.exists():
        raise FileExistsError("Refusing to overwrite an existing vector store")
    store.add(chunks, embedder.embed([chunk.text for chunk in chunks]))
    store.save()
    return store


class PolicyRetriever:
    """Returns source-attributed informational excerpts; it makes no decisions."""

    def __init__(self, store: FaissVectorStore, embedder: Embedder) -> None:
        if store.dimension != embedder.dimension:
            raise ValueError("Embedder and vector store dimensions differ")
        self.store, self.embedder = store, embedder

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        if not query or not query.strip():
            raise ValueError("Retrieval query cannot be empty")
        results = self.store.search(self.embedder.embed([query])[0], top_k)
        return [RetrievalResult(chunk_id=chunk.chunk_id, document_id=chunk.document_id, source_path=chunk.source_path, score=score, text=chunk.text, metadata=chunk.metadata) for chunk, score in results]


def load_policy_retriever(config_path: str | Path = PROJECT_ROOT / "configs" / "rag.yaml") -> PolicyRetriever | None:
    """Load a persisted retrieval index, returning ``None`` when none exists.

    The API must remain useful while ``data/documents`` is empty.  Therefore it
    never ingests documents or creates an index at request time; an operator
    must explicitly build an approved-document index first.
    """
    settings = load_rag_settings(config_path)
    if not (settings.vector_store / "chunks.faiss").is_file() or not (settings.vector_store / "chunks.json").is_file():
        return None
    embedder = SentenceTransformerEmbedder(settings.embedding_model)
    return PolicyRetriever(FaissVectorStore.load(settings.vector_store), embedder)
