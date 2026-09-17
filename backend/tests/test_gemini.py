from __future__ import annotations

import unittest

from src.gemini import GeminiExplanationSettings, GroundedExplanationService, build_grounded_prompt
from src.rag import RetrievalResult


ANALYSIS = {"provisional_overall_severity": "moderate", "detections": [{"class_name": "moderate", "confidence": 0.4}], "review": {"human_decision_required": True}}
EVIDENCE = [RetrievalResult("doc:0", "doc", "process.md", 0.8, "Review image evidence before recording a decision.", {"source_path": "process.md"})]


class FakeResponse:
    text = "Model evidence indicates provisional moderate severity. Policy/process evidence: review the image evidence [process.md#doc:0]."


class FakeModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
    def generate_content(self, **kwargs: str) -> FakeResponse:
        self.calls.append(kwargs); return FakeResponse()


class FakeClient:
    def __init__(self) -> None:
        self.models = FakeModels()


class GeminiTests(unittest.TestCase):
    def test_grounded_generation_preserves_separate_citations(self) -> None:
        client = FakeClient()
        result = GroundedExplanationService(GeminiExplanationSettings(), client=client, api_key=None).explain(ANALYSIS, EVIDENCE)
        self.assertEqual(result["status"], "grounded")
        self.assertEqual(result["citations"][0]["source_path"], "process.md")
        self.assertTrue(result["human_review_required"])
        self.assertIn("MODEL_EVIDENCE", client.models.calls[0]["contents"])
        self.assertIn("RETRIEVED_EVIDENCE", client.models.calls[0]["contents"])

    def test_empty_evidence_never_calls_gemini(self) -> None:
        client = FakeClient()
        result = GroundedExplanationService(client=client, api_key=None).explain(ANALYSIS, [])
        self.assertEqual(result["status"], "evidence_unavailable")
        self.assertFalse(client.models.calls)
        self.assertIn("Do not infer", result["explanation"])

    def test_missing_api_configuration_returns_safe_fallback(self) -> None:
        result = GroundedExplanationService(api_key="").explain(ANALYSIS, EVIDENCE)
        self.assertEqual(result["status"], "generation_unavailable")
        self.assertIn("human reviewer", result["explanation"])

    def test_gemini_failure_returns_safe_fallback(self) -> None:
        class BrokenModels:
            def generate_content(self, **_: str) -> None: raise RuntimeError("offline")
        class BrokenClient: models = BrokenModels()
        result = GroundedExplanationService(client=BrokenClient(), api_key=None).explain(ANALYSIS, EVIDENCE)
        self.assertEqual(result["status"], "generation_unavailable")

