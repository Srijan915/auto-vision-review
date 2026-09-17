"""Grounded, reviewer-facing Gemini explanations for ClaimSense evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

import yaml

from src.config import get_gemini_api_key
from src.rag import RetrievalResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class GeminiClient(Protocol):
    class models:  # pragma: no cover - describes google-genai's dynamic API
        @staticmethod
        def generate_content(*, model: str, contents: str) -> Any: ...


@dataclass(frozen=True)
class GeminiExplanationSettings:
    model: str = "gemini-3.6-flash"
    max_evidence_chunks: int = 3


def load_gemini_settings(config_path: str | Path = PROJECT_ROOT / "configs/gemini.yaml") -> GeminiExplanationSettings:
    values = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError("Gemini configuration must be a mapping")
    return GeminiExplanationSettings(**values)


def _citations(evidence: Sequence[RetrievalResult]) -> list[dict[str, Any]]:
    return [
        {"source_path": item.source_path, "chunk_id": item.chunk_id, "score": item.score}
        for item in evidence
    ]


def _model_evidence(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "provisional_overall_severity": analysis.get("provisional_overall_severity", "no_detection"),
        "detections": [
            {"class_name": item.get("class_name"), "confidence": item.get("confidence"), "bounding_box_xyxy": item.get("bounding_box_xyxy")}
            for item in analysis.get("detections", [])
        ],
        "review": analysis.get("review", {"human_decision_required": True}),
    }


def build_grounded_prompt(analysis: dict[str, Any], evidence: Sequence[RetrievalResult]) -> str:
    """Build one concise prompt requiring claims to stay within supplied evidence."""
    model_evidence = _model_evidence(analysis)
    sources = [{"source": item.source_path, "chunk": item.chunk_id, "text": item.text} for item in evidence]
    return (
        "Write a concise reviewer-facing explanation using only MODEL_EVIDENCE and RETRIEVED_EVIDENCE; "
        "separate model observations from policy/process excerpts; cite sources as [source_path#chunk_id]; "
        "if policy evidence is insufficient say so; do not infer or decide approval, coverage, payout, liability, fraud, repair cost, or legal responsibility; "
        f"MODEL_EVIDENCE={model_evidence}; RETRIEVED_EVIDENCE={sources}"
    )


class GroundedExplanationService:
    """Creates explanations only when both approved evidence and Gemini configuration exist."""

    def __init__(self, settings: GeminiExplanationSettings | None = None, client: GeminiClient | None = None, api_key: str | None = None) -> None:
        self.settings = settings or load_gemini_settings()
        self._client = client
        self._api_key = api_key if api_key is not None else get_gemini_api_key()

    def _client_or_none(self) -> GeminiClient | None:
        if self._client is not None:
            return self._client
        if not self._api_key:
            return None
        from google import genai

        self._client = genai.Client(api_key=self._api_key)
        return self._client

    def explain(self, damage_analysis: dict[str, Any], retrieved_evidence: Sequence[RetrievalResult]) -> dict[str, Any]:
        evidence = list(retrieved_evidence)[: self.settings.max_evidence_chunks]
        response = {
            "model_evidence": _model_evidence(damage_analysis),
            "retrieved_evidence": [
                {"source_path": item.source_path, "chunk_id": item.chunk_id, "score": item.score, "text": item.text}
                for item in evidence
            ],
            "citations": _citations(evidence),
            "human_review_required": True,
            "decision_boundary": "No approval, coverage, payout, liability, fraud, repair-cost, or legal decision is produced.",
        }
        if not evidence:
            return {**response, "status": "evidence_unavailable", "explanation": "No approved policy or process evidence was retrieved. Do not infer missing policy information; a human reviewer must consult the applicable source."}
        client = self._client_or_none()
        if client is None:
            return {**response, "status": "generation_unavailable", "explanation": "Retrieved policy/process evidence is available above, but Gemini is not configured. A human reviewer must interpret the cited sources."}
        try:
            generated = client.models.generate_content(model=self.settings.model, contents=build_grounded_prompt(damage_analysis, evidence))
            text = getattr(generated, "text", "").strip()
            if not text:
                raise ValueError("Gemini returned an empty explanation")
        except Exception:
            return {**response, "status": "generation_unavailable", "explanation": "Gemini explanation generation is unavailable. A human reviewer must interpret the cited model and policy/process evidence."}
        return {**response, "status": "grounded", "explanation": text}


def generate_response(prompt: str) -> str:
    """Compatibility helper for direct configured Gemini use; prefer the grounded service."""
    service = GroundedExplanationService()
    client = service._client_or_none()
    if client is None:
        raise RuntimeError("Gemini is not configured")
    return client.models.generate_content(model=service.settings.model, contents=prompt).text
