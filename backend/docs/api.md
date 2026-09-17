# ClaimSense API

Run the service with the existing environment:

```powershell
.\.venv\Scripts\uvicorn.exe src.api:app --reload
```

Endpoints: `POST /assessments` uploads a supported image and creates an
evidence-only assessment; `GET /assessments/{id}` returns the complete
assessment/audit record; `GET /assessments/{id}/image` returns its validated
original upload; `POST /assessments/{id}/explanation` requests a grounded
explanation; and `PUT /assessments/{id}/review` submits or updates a human
reviewer action. A review payload has `reviewer_id`, `action`, and the
human-authored `final_decision`, plus optional `reviewer_severity` (`minor`,
`moderate`, `severe`, or `no_detection`) and `reviewer_notes`. Each update
retains the prior entry in `review_history`; it never overwrites the audit
trail. `POST /claims`, `GET /claims/{id}`, and
`POST /claims/{id}/human-decision` remain deprecated compatibility aliases.

Assessments persist locally in SQLite at `data/claimsense_assessments.sqlite3`.
The database stores structured assessment metadata and evidence references; the
accepted image remains in the upload directory. This is appropriate for local
development, not a multi-user production deployment.
Uploads are limited to 10 MB and JPG/JPEG/PNG/WEBP, validated before inference.
The API exposes model evidence and retrieved sources separately. Empty RAG and
unconfigured Gemini are handled without inference of missing policy material.
Each accepted upload records a SHA-256 digest, size, image dimensions, original
filename, content type, validation time, retrieval status, and a timestamped
audit trail. The stored analysis retains every model detection, confidence, and
bounding box. RAG uses an existing `embeddings/policy_store/` only; the API
does not ingest documents or create an index during a request. When the index
is absent (as it is while `data/documents/` is empty), the claim remains
available with `retrieval.status = "evidence_unavailable"`.

FastAPI is the only backend dependency added for this phase. Start the service
after activating or directly using the existing `.venv` as shown above.

No endpoint automatically approves/rejects a claim or decides coverage, payout,
liability, fraud, repair cost, or legal responsibility. The decision endpoint
records a human's action and decision only; all AI output remains evidence for
the reviewer.
