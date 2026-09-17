"""End-to-end integration verification of ClaimSense pipeline."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.api import AppServices, ClaimStore, create_app
from src.config import get_gemini_api_key
from src.damage_model import SeverityDetector
from src.gemini import GroundedExplanationService
from src.preprocessing import validate_inference_image
from src.rag import load_policy_retriever


class IntegrationFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_dir = Path(self.temp_dir.name) / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(self.temp_dir.name) / "test_assessments.sqlite3"
        self.store = ClaimStore(self.db_path)

        # Real detector, real RAG retriever, real explainer (using .env config)
        self.detector = SeverityDetector()
        self.retriever = load_policy_retriever()
        self.explainer = GroundedExplanationService()

        self.services = AppServices(
            detector=self.detector,
            retriever=self.retriever,
            explainer=self.explainer,
            store=self.store,
            upload_directory=self.upload_dir,
        )

        try:
            from test_api import ApiTestClient
        except ImportError:
            from tests.test_api import ApiTestClient
        self.client = ApiTestClient(create_app(self.services))

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_full_pipeline_trace_with_real_image(self) -> None:
        """Trace one real image through preprocessing -> YOLO -> RAG -> Gemini -> human review -> SQLite."""
        # Locate real test image
        real_image_path = self.project_root / "data" / "uploads" / "03cbba60c7024430a413608d57ae75a0.jpg"
        if not real_image_path.is_file():
            # Fallback to generated valid image if sample image missing
            buffer = io.BytesIO()
            Image.new("RGB", (640, 640), "red").save(buffer, format="JPEG")
            image_bytes = buffer.getvalue()
            image_filename = "synthetic_damage.jpg"
        else:
            image_bytes = real_image_path.read_bytes()
            image_filename = real_image_path.name

        # 1. Preprocessing check
        validated = validate_inference_image(real_image_path if real_image_path.is_file() else io.BytesIO(image_bytes))
        self.assertGreater(validated.width, 0)
        self.assertGreater(validated.height, 0)
        self.assertIn(validated.format.upper(), ("JPEG", "JPG", "PNG", "WEBP"))

        # 2. Upload and create assessment: triggers YOLO detection + RAG retrieval
        resp = self.client.post("/assessments", files={"image": (image_filename, image_bytes, "image/jpeg")})
        self.assertEqual(resp.status_code, 201)
        assessment = resp.json()
        assessment_id = assessment["assessment_id"]

        # Verify YOLO detection evidence
        analysis = assessment["analysis"]
        self.assertIn(analysis["provisional_overall_severity"], ("minor", "moderate", "severe", "no_detection"))
        self.assertTrue(assessment["human_review_required"])
        self.assertEqual(assessment["status"], "awaiting_human_review")

        # Verify RAG retrieval from safety_references.md
        retrieval = assessment["retrieval"]
        self.assertEqual(retrieval["status"], "retrieved")
        self.assertGreater(len(assessment["retrieved_evidence"]), 0)
        self.assertEqual(assessment["retrieved_evidence"][0]["source_path"], "safety_references.md")

        # 3. Gemini grounded explanation
        exp_resp = self.client.post(f"/assessments/{assessment_id}/explanation")
        self.assertEqual(exp_resp.status_code, 200)
        explanation = exp_resp.json()

        api_key = get_gemini_api_key()
        if api_key:
            self.assertEqual(explanation["status"], "grounded")
            self.assertGreater(len(explanation["citations"]), 0)
            for citation in explanation["citations"]:
                self.assertEqual(citation["source_path"], "safety_references.md")
        else:
            self.assertEqual(explanation["status"], "generation_unavailable")

        # Decision boundary assertion: no claim decision, payout, or coverage
        self.assertIn("decision_boundary", explanation)
        self.assertNotIn("payout", explanation["explanation"].lower())
        self.assertNotIn("claim approved", explanation["explanation"].lower())
        self.assertNotIn("claim denied", explanation["explanation"].lower())

        # 4. Human review state
        review_payload = {
            "reviewer_id": "reviewer_integration_test",
            "action": "assessment_signoff",
            "final_decision": "review_complete",
            "reviewer_severity": analysis["provisional_overall_severity"],
            "reviewer_notes": "Reviewed damage against safety reference guidance.",
        }
        rev_resp = self.client.put(f"/assessments/{assessment_id}/review", json=review_payload)
        self.assertEqual(rev_resp.status_code, 200)
        reviewed = rev_resp.json()
        self.assertEqual(reviewed["status"], "human_review_submitted")
        self.assertEqual(reviewed["human_decision"]["reviewer_id"], "reviewer_integration_test")
        self.assertEqual(reviewed["human_decision"]["final_decision"], "review_complete")

        # 5. SQLite persistence and audit trail verification
        reloaded = self.store.get(assessment_id)
        self.assertEqual(reloaded.status, "human_review_submitted")
        self.assertEqual(reloaded.human_decision["reviewer_id"], "reviewer_integration_test")
        self.assertEqual(len(reloaded.audit_events), 3)
        self.assertEqual(reloaded.audit_events[0]["event_type"], "claim_created")
        self.assertEqual(reloaded.audit_events[1]["event_type"], "explanation_requested")
        self.assertEqual(reloaded.audit_events[2]["event_type"], "human_review_submitted")
