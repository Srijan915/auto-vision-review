from __future__ import annotations

import asyncio
import io
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import httpx
from PIL import Image

from src.api import AppServices, ClaimStore, create_app
from src.damage_model import SeverityDetector
from src.gemini import GroundedExplanationService
from src.rag import RetrievalResult, load_policy_retriever


def image_payload() -> bytes:
    output = io.BytesIO(); Image.new("RGB", (32, 32), "white").save(output, format="JPEG"); return output.getvalue()


class FakeDetector:
    def predict(self, _: Path) -> dict:
        return {"provisional_overall_severity": "moderate", "detections": [{"class_name": "moderate", "confidence": 0.4}], "review": {"human_decision_required": True}}


class FakeRetriever:
    def retrieve(self, _: str) -> list[RetrievalResult]:
        return [RetrievalResult("policy:0", "policy", "process.md", 0.9, "Review evidence.", {"source_path": "process.md"})]


class FakeExplainer:
    def explain(self, _: dict, evidence: list[RetrievalResult]) -> dict:
        return {"status": "grounded", "explanation": "Review the evidence [process.md#policy:0].", "citations": [{"source_path": item.source_path, "chunk_id": item.chunk_id} for item in evidence], "human_review_required": True}


class FakeGenAiModels:
    def generate_content(self, **kwargs: object) -> object:
        class _Resp:
            text = "Grounding confirmed based on [safety_references.md#7bce3b092d3689df:0]."
        return _Resp()


class FakeGenAiClient:
    models = FakeGenAiModels()


class ApiTestClient:
    """Synchronous facade over the installed HTTPX ASGI transport for tests."""

    def __init__(self, app: object) -> None:
        self.app = app

    def request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(send())

    def get(self, path: str, **kwargs: object) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: object) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: object) -> httpx.Response:
        return self.request("PUT", path, **kwargs)


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        services = AppServices(detector=FakeDetector(), retriever=FakeRetriever(), explainer=FakeExplainer(), store=ClaimStore(), upload_directory=Path(self.temp.name) / "uploads")
        self.client = ApiTestClient(create_app(services))

    def tearDown(self) -> None: self.temp.cleanup()

    def test_reviewer_workflow_and_audit(self) -> None:
        response = self.client.post("/claims", files={"image": ("damage.jpg", image_payload(), "image/jpeg")})
        self.assertEqual(response.status_code, 201)
        claim = response.json(); claim_id = claim["claim_id"]
        self.assertTrue(claim["human_review_required"])
        self.assertEqual(claim["analysis"]["provisional_overall_severity"], "moderate")
        self.assertEqual(claim["upload_metadata"]["original_filename"], "damage.jpg")
        self.assertEqual(len(claim["upload_metadata"]["sha256"]), 64)
        self.assertEqual(claim["retrieval"]["status"], "retrieved")
        explanation = self.client.post(f"/assessments/{claim_id}/explanation")
        self.assertEqual(explanation.json()["citations"][0]["source_path"], "process.md")
        image = self.client.get(f"/assessments/{claim_id}/image")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers["content-type"], "image/jpeg")
        decision = self.client.post(f"/claims/{claim_id}/human-decision", json={"reviewer_id": "reviewer-1", "decision": "needs_more_information", "rationale": "Image evidence needs confirmation."})
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.json()["status"], "human_decision_recorded")
        self.assertEqual(decision.json()["human_decision"]["recorded_by"], "human_reviewer")
        self.assertGreaterEqual(len(decision.json()["audit_events"]), 3)

    def test_assessment_review_updates_preserve_human_history(self) -> None:
        assessment = self.client.post("/assessments", files={"image": ("damage.jpg", image_payload(), "image/jpeg")})
        self.assertEqual(assessment.status_code, 201)
        assessment_id = assessment.json()["assessment_id"]
        first = self.client.put(f"/assessments/{assessment_id}/review", json={
            "reviewer_id": "reviewer-1", "action": "initial_review",
            "final_decision": "needs_more_information", "reviewer_severity": "minor",
            "reviewer_notes": "Bounding box requires a clearer image.",
        })
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["status"], "human_review_submitted")
        self.assertEqual(first.json()["human_decision"]["reviewer_severity"], "minor")
        second = self.client.put(f"/assessments/{assessment_id}/review", json={
            "reviewer_id": "reviewer-2", "action": "supervisor_update",
            "final_decision": "review_complete", "reviewer_severity": "moderate",
            "reviewer_notes": "Reviewer recorded final assessment notes.",
        })
        self.assertEqual(second.status_code, 200)
        payload = second.json()
        self.assertEqual(payload["status"], "human_review_updated")
        self.assertEqual(len(payload["review_history"]), 2)
        self.assertEqual(payload["review_history"][0]["reviewer_id"], "reviewer-1")
        self.assertEqual(payload["human_decision"]["reviewer_id"], "reviewer-2")
        self.assertEqual(payload["audit_events"][-1]["event_type"], "human_review_updated")

    def test_assessment_persists_across_store_instances(self) -> None:
        database = Path(self.temp.name) / "assessments.sqlite3"
        first_services = AppServices(
            detector=FakeDetector(), retriever=FakeRetriever(), explainer=FakeExplainer(),
            store=ClaimStore(database), upload_directory=Path(self.temp.name) / "persisted-uploads",
        )
        first_client = ApiTestClient(create_app(first_services))
        created = first_client.post("/assessments", files={"image": ("damage.jpg", image_payload(), "image/jpeg")}).json()
        assessment_id = created["assessment_id"]
        first_client.put(f"/assessments/{assessment_id}/review", json={
            "reviewer_id": "reviewer-1", "action": "record_review",
            "final_decision": "review_complete", "reviewer_notes": "Recorded by a human reviewer.",
        })
        restored_services = AppServices(store=ClaimStore(database), upload_directory=Path(self.temp.name) / "restored-uploads")
        restored = ApiTestClient(create_app(restored_services)).get(f"/assessments/{assessment_id}")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["assessment_id"], assessment_id)
        self.assertEqual(restored.json()["human_decision"]["reviewer_id"], "reviewer-1")
        self.assertEqual(len(restored.json()["review_history"]), 1)
        first_services.store.close()
        restored_services.store.close()

    def test_invalid_upload_is_rejected(self) -> None:
        response = self.client.post("/claims", files={"image": ("notes.txt", b"not an image", "text/plain")})
        self.assertEqual(response.status_code, 415)

    def test_empty_rag_is_graceful(self) -> None:
        with patch("src.api.load_policy_retriever", return_value=None):
            services = AppServices(detector=FakeDetector(), retriever=None, explainer=FakeExplainer(), store=ClaimStore(), upload_directory=Path(self.temp.name) / "empty")
            client = ApiTestClient(create_app(services))
            claim_id = client.post("/claims", files={"image": ("damage.jpg", image_payload(), "image/jpeg")}).json()["claim_id"]
            result = client.post(f"/claims/{claim_id}/explanation").json()
            self.assertEqual(result["status"], "grounded")
            self.assertEqual(result["citations"], [])

    def test_corrupt_image_and_missing_claim_are_safe_errors(self) -> None:
        corrupt = self.client.post("/claims", files={"image": ("damage.jpg", b"not an image", "image/jpeg")})
        self.assertEqual(corrupt.status_code, 422)
        missing = self.client.get("/claims/not-a-claim")
        self.assertEqual(missing.status_code, 404)

    def test_default_empty_rag_reports_evidence_unavailable(self) -> None:
        with patch("src.api.load_policy_retriever", return_value=None):
            services = AppServices(detector=FakeDetector(), explainer=FakeExplainer(), store=ClaimStore(), upload_directory=Path(self.temp.name) / "default-empty")
            client = ApiTestClient(create_app(services))
            response = client.post("/claims", files={"image": ("damage.jpg", image_payload(), "image/jpeg")})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["retrieval"]["status"], "evidence_unavailable")

    def test_end_to_end_real_model_rag_and_audit_integration(self) -> None:
        database = Path(self.temp.name) / "e2e_assessments.sqlite3"
        store = ClaimStore(database)
        services = AppServices(
            detector=SeverityDetector(),
            retriever=load_policy_retriever(),
            explainer=GroundedExplanationService(client=FakeGenAiClient()),
            store=store,
            upload_directory=Path(self.temp.name) / "e2e-uploads",
        )
        client = ApiTestClient(create_app(services))
        response = client.post("/assessments", files={"image": ("damage.jpg", image_payload(), "image/jpeg")})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        assessment_id = data["assessment_id"]
        self.assertEqual(data["status"], "awaiting_human_review")
        self.assertEqual(data["retrieval"]["status"], "retrieved")
        self.assertTrue(len(data["retrieved_evidence"]) > 0)
        self.assertEqual(data["retrieved_evidence"][0]["source_path"], "safety_references.md")

        exp_resp = client.post(f"/assessments/{assessment_id}/explanation")
        self.assertEqual(exp_resp.status_code, 200)
        exp_data = exp_resp.json()
        self.assertEqual(exp_data["status"], "grounded")
        self.assertTrue(len(exp_data["citations"]) > 0)
        self.assertEqual(exp_data["citations"][0]["source_path"], "safety_references.md")

        rev_resp = client.put(f"/assessments/{assessment_id}/review", json={
            "reviewer_id": "test_reviewer",
            "action": "completed_review",
            "final_decision": "review_complete",
            "reviewer_severity": "moderate",
            "reviewer_notes": "Verified against safety references.",
        })
        self.assertEqual(rev_resp.status_code, 200)
        rev_data = rev_resp.json()
        self.assertEqual(rev_data["status"], "human_review_submitted")
        self.assertEqual(rev_data["human_decision"]["reviewer_id"], "test_reviewer")

        reloaded = store.get(assessment_id)
        self.assertEqual(reloaded.status, "human_review_submitted")
        self.assertEqual(len(reloaded.audit_events), 3)
        self.assertEqual(reloaded.audit_events[0]["event_type"], "claim_created")
        self.assertEqual(reloaded.audit_events[1]["event_type"], "explanation_requested")
        self.assertEqual(reloaded.audit_events[2]["event_type"], "human_review_submitted")
        store.close()
