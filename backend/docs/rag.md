# ClaimSense document retrieval

ClaimSense retrieves source-attributed excerpts from approved internal policy or
process documents. It supports UTF-8 `.txt`, `.md`, and `.json` documents placed
under `data/documents/`. Empty or unsupported documents are not indexed.

The ingestion pipeline chunks text deterministically, embeds chunks, and writes
a local FAISS index plus JSON metadata in `embeddings/policy_store/`. Metadata
preserves each source-relative path, source SHA-256, document ID, and chunk ID.
Existing vector stores are never overwritten by ingestion.

Use `SentenceTransformerEmbedder` with the configured `all-MiniLM-L6-v2` model
for real semantic retrieval. The test-only `HashingEmbedder` avoids downloads
and is not suitable for production retrieval quality.

Retrieved material is informational evidence for a human reviewer. It does not
make or recommend coverage, payout, approval, liability, fraud, repair-cost, or
legal decisions.
