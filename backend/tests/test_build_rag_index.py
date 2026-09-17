from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.build_rag_index import EmptyCorpusError, build_rag_index, main
from src.embeddings import HashingEmbedder
from src.rag import PolicyRetriever
from src.vector_store import FaissVectorStore


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class BuildRagIndexTests(unittest.TestCase):
    def test_empty_corpus_handled_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "empty_docs"
            docs_dir.mkdir()
            store_dir = Path(temp_dir) / "store"

            report = build_rag_index(
                documents_root=docs_dir,
                vector_store=store_dir,
                use_hashing_embedder=True,
                allow_empty=True,
            )
            self.assertEqual(report.status, "empty_corpus")
            self.assertEqual(report.chunks_indexed, 0)
            self.assertEqual(report.documents_found, 0)
            self.assertFalse((store_dir / "chunks.faiss").exists())
            self.assertFalse((store_dir / "chunks.json").exists())

    def test_empty_corpus_strict_raises_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "empty_docs"
            docs_dir.mkdir()
            store_dir = Path(temp_dir) / "store"

            with self.assertRaises(EmptyCorpusError):
                build_rag_index(
                    documents_root=docs_dir,
                    vector_store=store_dir,
                    use_hashing_embedder=True,
                    allow_empty=False,
                )

    def test_nonexistent_documents_root_handled_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "does_not_exist"
            store_dir = Path(temp_dir) / "store"

            report = build_rag_index(
                documents_root=docs_dir,
                vector_store=store_dir,
                use_hashing_embedder=True,
                allow_empty=True,
            )
            self.assertEqual(report.status, "empty_corpus")
            self.assertEqual(report.chunks_indexed, 0)

    def test_ingest_documents_preserves_sha256_and_source_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()
            store_dir = Path(temp_dir) / "store"

            text_doc = docs_dir / "guide.txt"
            text_bytes = b"Standard operating guideline for inspection processes and evidence verification."
            text_doc.write_bytes(text_bytes)

            md_doc = docs_dir / "subfolder" / "notes.md"
            md_doc.parent.mkdir(parents=True)
            md_bytes = b"# Operational Notes\nDocument reviewer checklist and required audit fields."
            md_doc.write_bytes(md_bytes)

            json_doc = docs_dir / "data.json"
            json_data = {"key": "metadata", "value": "structured sample document"}
            json_doc.write_text(json.dumps(json_data), encoding="utf-8")
            json_bytes = json_doc.read_bytes()

            report = build_rag_index(
                documents_root=docs_dir,
                vector_store=store_dir,
                chunk_size=50,
                chunk_overlap=5,
                use_hashing_embedder=True,
                allow_empty=False,
            )
            self.assertEqual(report.status, "success")
            self.assertEqual(report.documents_found, 3)
            self.assertGreaterEqual(report.chunks_indexed, 3)

            self.assertTrue((store_dir / "chunks.faiss").is_file())
            self.assertTrue((store_dir / "chunks.json").is_file())

            loaded_store = FaissVectorStore.load(store_dir)
            self.assertEqual(len(loaded_store.chunks), report.chunks_indexed)

            expected_hashes = {
                "guide.txt": _sha256(text_bytes),
                "subfolder/notes.md": _sha256(md_bytes),
                "data.json": _sha256(json_bytes),
            }

            for chunk in loaded_store.chunks:
                self.assertIn(chunk.source_path, expected_hashes)
                self.assertEqual(chunk.source_sha256, expected_hashes[chunk.source_path])
                self.assertTrue(chunk.chunk_id.startswith(f"{chunk.document_id}:"))
                self.assertIn("document_type", chunk.metadata)
                self.assertEqual(chunk.metadata["source_path"], chunk.source_path)

            retriever = PolicyRetriever(loaded_store, HashingEmbedder(report.dimension))
            results = retriever.retrieve("inspection processes", top_k=2)
            self.assertTrue(len(results) > 0)
            self.assertIn(results[0].source_path, expected_hashes)

    def test_refuses_overwrite_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()
            store_dir = Path(temp_dir) / "store"

            (docs_dir / "file.txt").write_text("Document content for initial store.", encoding="utf-8")
            build_rag_index(
                documents_root=docs_dir,
                vector_store=store_dir,
                use_hashing_embedder=True,
            )

            with self.assertRaises(FileExistsError):
                build_rag_index(
                    documents_root=docs_dir,
                    vector_store=store_dir,
                    use_hashing_embedder=True,
                    overwrite=False,
                )

    def test_overwrites_with_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()
            store_dir = Path(temp_dir) / "store"

            doc1 = docs_dir / "file.txt"
            doc1.write_text("Initial text content before overwrite.", encoding="utf-8")
            first_report = build_rag_index(
                documents_root=docs_dir,
                vector_store=store_dir,
                use_hashing_embedder=True,
            )
            self.assertEqual(first_report.status, "success")

            doc1.write_text("Updated text content with substantially new wording for second run.", encoding="utf-8")
            second_report = build_rag_index(
                documents_root=docs_dir,
                vector_store=store_dir,
                use_hashing_embedder=True,
                overwrite=True,
            )
            self.assertEqual(second_report.status, "success")
            loaded = FaissVectorStore.load(store_dir)
            self.assertEqual(loaded.chunks[0].source_sha256, _sha256(doc1.read_bytes()))

    def test_skips_unsupported_extensions_and_empty_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()
            store_dir = Path(temp_dir) / "store"

            (docs_dir / "empty.txt").write_text("", encoding="utf-8")
            (docs_dir / "manual.pdf").write_bytes(b"%PDF-1.4 binary content")
            (docs_dir / "tool.bin").write_bytes(b"\x00\x01\x02\x03")
            (docs_dir / "valid.md").write_text("Valid text chunk for index creation.", encoding="utf-8")

            report = build_rag_index(
                documents_root=docs_dir,
                vector_store=store_dir,
                use_hashing_embedder=True,
            )
            self.assertEqual(report.status, "success")
            self.assertEqual(report.documents_found, 1)
            loaded = FaissVectorStore.load(store_dir)
            self.assertEqual(len(loaded.chunks), 1)
            self.assertEqual(loaded.chunks[0].source_path, "valid.md")

    def test_cli_empty_corpus_default_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "empty"
            docs_dir.mkdir()
            store_dir = Path(temp_dir) / "store"

            code = main([
                "--documents-root", str(docs_dir),
                "--vector-store", str(store_dir),
                "--use-hashing-embedder",
            ])
            self.assertEqual(code, 0)

    def test_cli_empty_corpus_strict_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "empty"
            docs_dir.mkdir()
            store_dir = Path(temp_dir) / "store"

            code = main([
                "--documents-root", str(docs_dir),
                "--vector-store", str(store_dir),
                "--use-hashing-embedder",
                "--strict",
            ])
            self.assertEqual(code, 1)

    def test_cli_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()
            store_dir = Path(temp_dir) / "store"

            (docs_dir / "sample.md").write_text("Sample markdown notes for CLI verification.", encoding="utf-8")

            captured = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = captured
                code = main([
                    "--documents-root", str(docs_dir),
                    "--vector-store", str(store_dir),
                    "--use-hashing-embedder",
                    "--json",
                ])
            finally:
                sys.stdout = old_stdout

            self.assertEqual(code, 0)
            data = json.loads(captured.getvalue())
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["documents_found"], 1)
            self.assertTrue(data["chunks_indexed"] >= 1)

    def test_cli_refuses_overwrite_then_succeeds_with_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()
            store_dir = Path(temp_dir) / "store"

            (docs_dir / "sample.txt").write_text("Sample text content for test.", encoding="utf-8")

            # First build succeeds
            code1 = main([
                "--documents-root", str(docs_dir),
                "--vector-store", str(store_dir),
                "--use-hashing-embedder",
            ])
            self.assertEqual(code1, 0)

            # Re-running without overwrite flag fails with code 1
            code2 = main([
                "--documents-root", str(docs_dir),
                "--vector-store", str(store_dir),
                "--use-hashing-embedder",
            ])
            self.assertEqual(code2, 1)

            # Re-running with --overwrite flag succeeds with code 0
            code3 = main([
                "--documents-root", str(docs_dir),
                "--vector-store", str(store_dir),
                "--use-hashing-embedder",
                "--overwrite",
            ])
            self.assertEqual(code3, 0)
