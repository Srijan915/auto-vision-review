"""ClaimSense reviewer-facing FastAPI service; never makes insurance decisions."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.damage_model import SeverityDetector
from src.gemini import GroundedExplanationService
from src.preprocessing import InvalidImageError, SUPPORTED_IMAGE_SUFFIXES, validate_inference_image
from src.rag import RetrievalResult, load_policy_retriever


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class Detector(Protocol):
    def predict(self, image_path: str | Path) -> dict[str, Any]: ...


class Explainer(Protocol):
    def explain(self, damage_analysis: dict[str, Any], retrieved_evidence: list[RetrievalResult]) -> dict[str, Any]: ...


class Retriever(Protocol):
    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]: ...


@dataclass(frozen=True)
class ValidatedUpload:
    path: Path
    metadata: dict[str, Any]


@dataclass
class Claim:
    claim_id: str
    created_at: str
    updated_at: str
    image_path: str
    upload_metadata: dict[str, Any]
    analysis: dict[str, Any]
    evidence: list[RetrievalResult]
    retrieval: dict[str, Any]
    status: str = "awaiting_human_review"
    explanation: dict[str, Any] | None = None
    human_decision: dict[str, Any] | None = None
    review_history: list[dict[str, Any]] = field(default_factory=list)
    audit_events: list[dict[str, Any]] = field(default_factory=list)


class ClaimStore:
    """Small local SQLite repository for audit-friendly assessment records.

    It deliberately persists only structured record metadata and paths to the
    already-stored evidence images. It does not contain policy or decision
    logic. Passing no path creates an isolated in-memory store for tests.
    """
    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = str(database_path) if database_path is not None else ":memory:"
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self._lock = threading.RLock()
        with self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS assessments (assessment_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, record_json TEXT NOT NULL)"
            )

    def create(self, claim: Claim) -> None:
        record = json.dumps(_serialize_claim(claim), ensure_ascii=False, sort_keys=True)
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO assessments (assessment_id, created_at, updated_at, record_json) VALUES (?, ?, ?, ?)",
                (claim.claim_id, claim.created_at, claim.updated_at, record),
            )

    def save(self, claim: Claim) -> None:
        record = json.dumps(_serialize_claim(claim), ensure_ascii=False, sort_keys=True)
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE assessments SET updated_at = ?, record_json = ? WHERE assessment_id = ?",
                (claim.updated_at, record, claim.claim_id),
            )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="Assessment not found")

    def get(self, claim_id: str) -> Claim:
        with self._lock:
            row = self._connection.execute(
                "SELECT record_json FROM assessments WHERE assessment_id = ?", (claim_id,)
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return _claim_from_record(json.loads(row[0]))

    def list_all(self) -> list[Claim]:
        with self._lock:
          rows = self._connection.execute(
            "SELECT record_json FROM assessments ORDER BY created_at DESC"
        ).fetchall()
        return [_claim_from_record(json.loads(row[0])) for row in rows]
    def close(self) -> None:
        self._connection.close()


@dataclass
class AppServices:
    detector: Detector | None = None
    retriever: Retriever | None = None
    explainer: Explainer | None = None
    store: ClaimStore = field(default_factory=lambda: ClaimStore(PROJECT_ROOT / "data" / "claimsense_assessments.sqlite3"))
    upload_directory: Path = PROJECT_ROOT / "data" / "uploads"
    _retriever_checked: bool = field(default=False, init=False, repr=False)
    _retrieval_unavailable_reason: str | None = field(default=None, init=False, repr=False)

    def get_detector(self) -> Detector:
        if self.detector is None:
            self.detector = SeverityDetector()
        return self.detector

    def get_explainer(self) -> Explainer:
        if self.explainer is None:
            self.explainer = GroundedExplanationService()
        return self.explainer

    def retrieve(self, query: str) -> tuple[list[RetrievalResult], dict[str, Any]]:
        """Retrieve approved evidence, without making RAG availability fatal."""
        if self.retriever is None and not self._retriever_checked:
            self._retriever_checked = True
            try:
                self.retriever = load_policy_retriever()
            except Exception:
                # Do not expose configuration details or make an evidence-free
                # claim fail. A human reviewer can still inspect the image.
                self._retrieval_unavailable_reason = "retriever_initialization_failed"
        if self.retriever is None:
            return [], {
                "status": "evidence_unavailable",
                "reason": self._retrieval_unavailable_reason or "approved_document_index_not_available",
                "result_count": 0,
            }
        try:
            evidence = self.retriever.retrieve(query)
        except Exception:
            return [], {"status": "retrieval_unavailable", "reason": "retrieval_failed", "result_count": 0}
        return evidence, {"status": "retrieved", "result_count": len(evidence)}


class HumanDecisionRequest(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=100)
    decision: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=1, max_length=4000)


class ReviewerDecisionRequest(BaseModel):
    """A human-authored review record; none of its fields are AI-generated."""

    reviewer_id: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=100)
    final_decision: str = Field(min_length=1, max_length=100)
    reviewer_severity: Literal["minor", "moderate", "severe", "no_detection"] | None = None
    reviewer_notes: str | None = Field(default=None, max_length=4000)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(event_type: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"at": _now(), "event_type": event_type, "details": details or {}}


def _serialize_evidence(evidence: list[RetrievalResult]) -> list[dict[str, Any]]:
    return [{"chunk_id": item.chunk_id, "document_id": item.document_id, "source_path": item.source_path, "score": item.score, "text": item.text, "metadata": item.metadata} for item in evidence]


def _serialize_claim(claim: Claim) -> dict[str, Any]:
    return {
        "assessment_id": claim.claim_id, "claim_id": claim.claim_id,
        "created_at": claim.created_at, "updated_at": claim.updated_at, "status": claim.status,
        "image_path": claim.image_path, "upload_metadata": claim.upload_metadata,
        "analysis": claim.analysis, "retrieval": claim.retrieval,
        "retrieved_evidence": _serialize_evidence(claim.evidence), "explanation": claim.explanation,
        "human_decision": claim.human_decision, "review_history": claim.review_history,
        "audit_events": claim.audit_events,
        "human_review_required": True,
    }


def _claim_from_record(record: dict[str, Any]) -> Claim:
    """Rehydrate SQLite JSON without losing retrieval source metadata."""
    evidence = [
        RetrievalResult(
            chunk_id=item["chunk_id"], document_id=item["document_id"],
            source_path=item["source_path"], score=float(item["score"]),
            text=item["text"], metadata=item.get("metadata", {}),
        )
        for item in record.get("retrieved_evidence", [])
    ]
    return Claim(
        claim_id=record["claim_id"], created_at=record["created_at"],
        updated_at=record.get("updated_at", record["created_at"]), image_path=record["image_path"],
        upload_metadata=record["upload_metadata"], analysis=record["analysis"], evidence=evidence,
        retrieval=record["retrieval"], status=record.get("status", "awaiting_human_review"),
        explanation=record.get("explanation"), human_decision=record.get("human_decision"),
        review_history=record.get("review_history", []), audit_events=record.get("audit_events", []),
    )


async def _save_upload(upload: UploadFile, directory: Path) -> ValidatedUpload:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        raise HTTPException(status_code=415, detail="Only JPG, JPEG, PNG, and WEBP images are supported")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{uuid4().hex}{suffix}"
    size = 0
    digest = hashlib.sha256()
    try:
        with destination.open("wb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Image exceeds the 10 MB upload limit")
                target.write(chunk)
                digest.update(chunk)
        image = validate_inference_image(destination)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except InvalidImageError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Uploaded file is not a readable supported image") from exc
    finally:
        await upload.close()
    return ValidatedUpload(destination, {
        "original_filename": Path(upload.filename or "").name,
        "content_type": upload.content_type,
        "byte_size": size,
        "sha256": digest.hexdigest(),
        "width": image.width,
        "height": image.height,
        "format": image.format,
        "validated_at": _now(),
    })


def create_app(services: AppServices | None = None) -> FastAPI:
    services = services or AppServices()
    app = FastAPI(title="ClaimSense API", version="0.1.0", description="Human-in-the-loop vehicle-damage evidence workflow.")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "decision_boundary": "human_review_required"}

    async def create_assessment_record(image: UploadFile) -> dict[str, Any]:
        upload = await _save_upload(image, services.upload_directory)
        try:
            analysis = services.get_detector().predict(upload.path)
        except Exception as exc:
            upload.path.unlink(missing_ok=True)
            raise HTTPException(status_code=503, detail="Damage analysis is currently unavailable") from exc
        query = f"vehicle damage {analysis.get('provisional_overall_severity', 'no_detection')} reviewer process"
        evidence, retrieval = services.retrieve(query)
        timestamp = _now()
        claim = Claim(
            claim_id=uuid4().hex, created_at=timestamp, updated_at=timestamp, image_path=str(upload.path),
            upload_metadata=upload.metadata, analysis=analysis, evidence=evidence, retrieval=retrieval,
        )
        claim.audit_events.append(_event("claim_created", {
            "analysis_status": analysis.get("provisional_overall_severity"),
            "detection_count": len(analysis.get("detections", [])),
            "evidence_count": len(evidence), "upload_sha256": upload.metadata["sha256"],
            "retrieval_status": retrieval["status"],
        }))
        services.store.create(claim)
        return _serialize_claim(claim)

    @app.post("/assessments", status_code=status.HTTP_201_CREATED)
    async def create_assessment(image: UploadFile = File(...)) -> dict[str, Any]:
        """Create an evidence-only assessment awaiting a human review."""
        return await create_assessment_record(image)

    @app.post("/claims", status_code=status.HTTP_201_CREATED, deprecated=True)
    async def create_claim(image: UploadFile = File(...)) -> dict[str, Any]:
        """Compatibility alias for ``POST /assessments``."""
        return await create_assessment_record(image)

    @app.get("/assessments")
    def list_assessments() -> list[dict[str, Any]]:
        return [_serialize_claim(claim) for claim in services.store.list_all()]

    @app.get("/assessments/{assessment_id}")
    def get_assessment(assessment_id: str) -> dict[str, Any]:
        return _serialize_claim(services.store.get(assessment_id))

    @app.get("/assessments/{assessment_id}/image")
    def get_assessment_image(assessment_id: str) -> FileResponse:
        """Return the validated upload associated with this assessment only."""
        claim = services.store.get(assessment_id)
        image_path = Path(claim.image_path)
        if not image_path.is_file():
            raise HTTPException(status_code=404, detail="Assessment image is no longer available")
        return FileResponse(image_path, media_type=claim.upload_metadata.get("content_type") or "application/octet-stream")

    @app.get("/claims/{claim_id}", deprecated=True)
    def get_claim(claim_id: str) -> dict[str, Any]:
        return _serialize_claim(services.store.get(claim_id))

    def generate_assessment_explanation(assessment_id: str) -> dict[str, Any]:
        claim = services.store.get(assessment_id)
        claim.explanation = services.get_explainer().explain(claim.analysis, claim.evidence)
        claim.audit_events.append(_event("explanation_requested", {"status": claim.explanation["status"], "citation_count": len(claim.explanation["citations"])}))
        claim.updated_at = _now()
        services.store.save(claim)
        return claim.explanation

    @app.post("/assessments/{assessment_id}/explanation")
    def generate_explanation(assessment_id: str) -> dict[str, Any]:
        return generate_assessment_explanation(assessment_id)

    @app.post("/claims/{claim_id}/explanation", deprecated=True)
    def generate_claim_explanation(claim_id: str) -> dict[str, Any]:
        return generate_assessment_explanation(claim_id)

    def apply_reviewer_decision(claim: Claim, request: ReviewerDecisionRequest, *, legacy: bool = False) -> dict[str, Any]:
        """Persist a human action without interpreting or evaluating it."""
        recorded_at = _now()
        review = {
            "reviewer_id": request.reviewer_id,
            "action": request.action,
            "decision": request.final_decision,  # Compatibility with the original response shape.
            "final_decision": request.final_decision,
            "reviewer_severity": request.reviewer_severity,
            "reviewer_notes": request.reviewer_notes,
            "recorded_at": recorded_at,
            "recorded_by": "human_reviewer",
        }
        is_update = bool(claim.review_history)
        claim.review_history.append(review)
        claim.human_decision = review
        claim.status = "human_decision_recorded" if legacy else (
            "human_review_updated" if is_update else "human_review_submitted"
        )
        claim.updated_at = recorded_at
        event_type = "human_decision_recorded" if legacy else (
            "human_review_updated" if is_update else "human_review_submitted"
        )
        claim.audit_events.append(_event(event_type, {
            "reviewer_id": request.reviewer_id, "action": request.action,
            "reviewer_severity": request.reviewer_severity,
        }))
        services.store.save(claim)
        return _serialize_claim(claim)

    @app.put("/assessments/{assessment_id}/review")
    def submit_or_update_review(assessment_id: str, request: ReviewerDecisionRequest) -> dict[str, Any]:
        """Submit or update a human review while retaining every prior review."""
        return apply_reviewer_decision(services.store.get(assessment_id), request)

    @app.post("/claims/{claim_id}/human-decision")
    def record_human_decision(claim_id: str, request: HumanDecisionRequest) -> dict[str, Any]:
        claim = services.store.get(claim_id)
        return apply_reviewer_decision(claim, ReviewerDecisionRequest(
            reviewer_id=request.reviewer_id, action="legacy_human_decision",
            final_decision=request.decision, reviewer_notes=request.rationale,
        ), legacy=True)

    return app


app = create_app()
