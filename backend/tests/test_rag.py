from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.embeddings import HashingEmbedder
from src.rag import PolicyRetriever, chunk_text, ingest_documents
from src.vector_store import FaissVectorStore


class RagTests(unittest.TestCase):
    def test_chunking_retrieval_persistence_and_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "documents"; root.mkdir()
            (root / "review.md").write_text("Human reviewers must inspect damage evidence before recording a claim decision.", encoding="utf-8")
            (root / "process.txt").write_text("Escalate unclear images to a reviewer. Retrieval is informational only.", encoding="utf-8")
            embedder = HashingEmbedder()
            store = ingest_documents(root, embedder, Path(directory) / "store", chunk_size=20, overlap=2)
            results = PolicyRetriever(store, embedder).retrieve("review damage evidence", top_k=2)
            restored = FaissVectorStore.load(Path(directory) / "store")
        self.assertEqual(len(store.chunks), 2)
        self.assertEqual(restored.index.ntotal, 2)
        self.assertTrue(results)
        self.assertEqual(results[0].source_path, "review.md")
        self.assertIn("source_path", results[0].metadata)

    def test_chunking_and_empty_corpus_fail_safely(self) -> None:
        self.assertEqual(chunk_text("one two three", chunk_size=2, overlap=1), ["one two", "two three", "three"])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                ingest_documents(directory, HashingEmbedder(), Path(directory) / "store")

    def test_approved_safety_references_document_and_retrieval(self) -> None:
        doc_path = Path(__file__).resolve().parents[1] / "data" / "documents" / "safety_references.md"
        self.assertTrue(doc_path.is_file())
        content = doc_path.read_text(encoding="utf-8")
        for ref_id in ("safety_001", "safety_002", "safety_003", "safety_004", "safety_005"):
            self.assertIn(f"## {ref_id}:", content)
        self.assertIn("https://www.nhtsa.gov/interpretations/30122-make-inoperative-alan-nappier-april-14", content)
        self.assertIn("https://www.nhtsa.gov/interpretations/2256y", content)
        self.assertIn("https://rts.i-car.com/crn-689.html", content)
        self.assertIn("https://www.midtronics.com/blog/disconnect-high-voltage-ev-battery-systems/", content)
        self.assertIn("https://www.nhtsa.gov/node/51671", content)
        self.assertIn("Not an Insurance Policy or Decision Rule", content)
        self.assertTrue(all(ord(c) < 128 for c in content))
        store_path = Path(__file__).resolve().parents[1] / "embeddings" / "policy_store"
        if (store_path / "chunks.faiss").is_file() and (store_path / "chunks.json").is_file():
            store = FaissVectorStore.load(store_path)
            self.assertEqual(len(store.chunks), 4)
            self.assertEqual(store.dimension, 384)
