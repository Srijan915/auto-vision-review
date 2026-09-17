"""Production-ready CLI to ingest approved UTF-8 documents and build the ClaimSense RAG index."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.embeddings import Embedder, HashingEmbedder, SentenceTransformerEmbedder
from src.rag import (
    SUPPORTED_DOCUMENT_SUFFIXES,
    ingest_documents,
    load_rag_settings,
)
from src.vector_store import FaissVectorStore


class EmptyCorpusError(ValueError):
    """Raised when the document directory contains no supported non-empty documents."""


@dataclass(frozen=True)
class IngestionReport:
    """Structured execution summary of the RAG document ingestion process."""

    status: str
    documents_root: Path
    vector_store: Path
    documents_found: int
    chunks_indexed: int
    dimension: int
    embedding_provider: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "documents_root": str(self.documents_root),
            "vector_store": str(self.vector_store),
            "documents_found": self.documents_found,
            "chunks_indexed": self.chunks_indexed,
            "dimension": self.dimension,
            "embedding_provider": self.embedding_provider,
            "message": self.message,
        }


def _resolve_project_path(candidate: str | Path) -> Path:
    path = Path(candidate)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _count_supported_documents(documents_root: Path) -> int:
    if not documents_root.is_dir():
        return 0
    count = 0
    for path in sorted(documents_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES:
            try:
                if path.read_text(encoding="utf-8").strip():
                    count += 1
            except (UnicodeDecodeError, OSError):
                continue
    return count


def build_rag_index(
    documents_root: str | Path | None = None,
    vector_store: str | Path | None = None,
    *,
    config_path: str | Path = PROJECT_ROOT / "configs" / "rag.yaml",
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    embedding_model: str | None = None,
    embedder: Embedder | None = None,
    use_hashing_embedder: bool = False,
    overwrite: bool = False,
    allow_empty: bool = True,
) -> IngestionReport:
    """Ingest approved UTF-8 documents and persist a FAISS index with source metadata.

    Preserves source path, source SHA-256 fingerprint, document ID, and chunk IDs.
    Handles an empty corpus safely without leaving corrupt or partial index files.
    """
    config_resolved = _resolve_project_path(config_path)
    settings = load_rag_settings(config_resolved)

    raw_config: dict[str, Any] = {}
    if config_resolved.is_file():
        try:
            loaded = yaml.safe_load(config_resolved.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                raw_config = loaded
        except Exception:
            raw_config = {}

    target_docs = _resolve_project_path(documents_root) if documents_root is not None else settings.documents_root
    target_store = _resolve_project_path(vector_store) if vector_store is not None else settings.vector_store
    chunk_size_words = chunk_size or int(raw_config.get("chunk_size_words", 300))
    chunk_overlap_words = chunk_overlap or int(raw_config.get("chunk_overlap_words", 50))
    model_name = embedding_model or settings.embedding_model

    doc_count = _count_supported_documents(target_docs)
    if doc_count == 0:
        if allow_empty:
            return IngestionReport(
                status="empty_corpus",
                documents_root=target_docs,
                vector_store=target_store,
                documents_found=0,
                chunks_indexed=0,
                dimension=0,
                embedding_provider="none",
                message=(
                    f"No supported non-empty documents ({', '.join(sorted(SUPPORTED_DOCUMENT_SUFFIXES))}) "
                    f"found in '{target_docs}'. Index was not created; retrieval safely remains "
                    f"in 'evidence_unavailable' state."
                ),
            )
        raise EmptyCorpusError(
            f"No supported non-empty documents found in '{target_docs}'. "
            f"Expected UTF-8 files with extensions: {', '.join(sorted(SUPPORTED_DOCUMENT_SUFFIXES))}."
        )

    index_file = target_store / "chunks.faiss"
    metadata_file = target_store / "chunks.json"
    if index_file.exists() or metadata_file.exists():
        if not overwrite:
            raise FileExistsError(
                f"Vector store already exists at '{target_store}'. Use --overwrite to replace it."
            )
        index_file.unlink(missing_ok=True)
        metadata_file.unlink(missing_ok=True)

    if embedder is not None:
        active_embedder = embedder
        provider_name = getattr(embedder, "model_name", embedder.__class__.__name__)
    elif use_hashing_embedder:
        active_embedder = HashingEmbedder()
        provider_name = "HashingEmbedder(test)"
    else:
        active_embedder = SentenceTransformerEmbedder(model_name)
        provider_name = f"SentenceTransformer({model_name})"

    try:
        store = ingest_documents(
            documents_root=target_docs,
            embedder=active_embedder,
            store_directory=target_store,
            chunk_size=chunk_size_words,
            overlap=chunk_overlap_words,
        )
    except ValueError as exc:
        if "No supported non-empty documents" in str(exc) and allow_empty:
            return IngestionReport(
                status="empty_corpus",
                documents_root=target_docs,
                vector_store=target_store,
                documents_found=0,
                chunks_indexed=0,
                dimension=0,
                embedding_provider="none",
                message=str(exc),
            )
        raise

    unique_docs = len({chunk.source_path for chunk in store.chunks})
    chunks_count = len(store.chunks)

    return IngestionReport(
        status="success",
        documents_root=target_docs,
        vector_store=target_store,
        documents_found=unique_docs,
        chunks_indexed=chunks_count,
        dimension=store.dimension,
        embedding_provider=provider_name,
        message=(
            f"Successfully indexed {unique_docs} document(s) ({chunks_count} chunks, "
            f"dimension {store.dimension}) into '{target_store}'."
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for ClaimSense RAG document ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest approved UTF-8 documents and persist a FAISS vector index for ClaimSense.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "rag.yaml",
        help="Path to RAG configuration YAML file (default: configs/rag.yaml).",
    )
    parser.add_argument(
        "--documents-root",
        type=Path,
        default=None,
        help="Source directory with approved UTF-8 documents (.txt, .md, .json). Defaults to config.",
    )
    parser.add_argument(
        "--vector-store",
        type=Path,
        default=None,
        help="Target directory for FAISS chunks.faiss and chunks.json. Defaults to config.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Chunk size in words (default from config: 300).",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=None,
        help="Chunk overlap in words (default from config: 50).",
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default=None,
        help="SentenceTransformer model name (default from config: all-MiniLM-L6-v2).",
    )
    parser.add_argument(
        "--use-hashing-embedder",
        action="store_true",
        help="Use deterministic offline hashing embedder for testing without downloading models.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing vector store in target directory if it exists.",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        default=True,
        help="Exit cleanly with code 0 if document corpus is empty (default: True).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if document corpus contains no supported documents.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print structured JSON output instead of plain text.",
    )

    args = parser.parse_args(argv)
    allow_empty = not args.strict if args.strict else args.allow_empty

    try:
        report = build_rag_index(
            documents_root=args.documents_root,
            vector_store=args.vector_store,
            config_path=args.config,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            embedding_model=args.embedding_model,
            use_hashing_embedder=args.use_hashing_embedder,
            overwrite=args.overwrite,
            allow_empty=allow_empty,
        )
    except EmptyCorpusError as exc:
        if args.json:
            print(json.dumps({"status": "error", "error_type": "EmptyCorpusError", "message": str(exc)}, indent=2))
        else:
            print(f"[ERROR] {exc}", file=sys.stderr)
            print("ClaimSense retrieval remains safely in 'evidence_unavailable' state.", file=sys.stderr)
        return 1
    except FileExistsError as exc:
        if args.json:
            print(json.dumps({"status": "error", "error_type": "FileExistsError", "message": str(exc)}, indent=2))
        else:
            print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error_type": exc.__class__.__name__, "message": str(exc)}, indent=2))
        else:
            print(f"[ERROR] Ingestion failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        if report.status == "empty_corpus":
            print(f"[INFO] {report.message}")
        else:
            print(f"[SUCCESS] {report.message}")
            print(f"  Documents root : {report.documents_root}")
            print(f"  Vector store   : {report.vector_store}")
            print(f"  Chunks indexed : {report.chunks_indexed}")
            print(f"  Dimension      : {report.dimension}")
            print(f"  Embedder       : {report.embedding_provider}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
