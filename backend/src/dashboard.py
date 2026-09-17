"""Streamlit reviewer dashboard backed exclusively by the ClaimSense API.

Run after starting the API server:
    .\.venv\Scripts\streamlit.exe run src\dashboard.py
"""

from __future__ import annotations

import io
import os
from typing import Any

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont


DEFAULT_API_URL = os.getenv("CLAIMSENSE_API_URL", "http://127.0.0.1:8000")
SEVERITIES = ("minor", "moderate", "severe", "no_detection")
SEVERITY_COLORS = {
    "minor": "#22c55e", "moderate": "#f59e0b", "severe": "#ef4444", "no_detection": "#64748b",
}


class ApiError(RuntimeError):
    """A user-safe API client error suitable for dashboard display."""


class ClaimSenseClient:
    """Minimal HTTP client. It contains no inference or review business logic."""

    def __init__(self, base_url: str, session: Any | None = None, timeout: float = 45.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        try:
            response = self.session.request(method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise ApiError("The ClaimSense API is unavailable. Start the backend and check the API URL.") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiError(f"API request failed ({response.status_code}): {detail}")
        return response

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health").json()

    def create_assessment(self, filename: str, content: bytes, content_type: str | None) -> dict[str, Any]:
        return self._request(
            "POST", "/assessments",
            files={"image": (filename, content, content_type or "application/octet-stream")},
        ).json()

    def get_assessment(self, assessment_id: str) -> dict[str, Any]:
        return self._request("GET", f"/assessments/{assessment_id}").json()

    def get_image(self, assessment_id: str) -> bytes:
        return self._request("GET", f"/assessments/{assessment_id}/image").content

    def generate_explanation(self, assessment_id: str) -> dict[str, Any]:
        return self._request("POST", f"/assessments/{assessment_id}/explanation").json()

    def submit_review(self, assessment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/assessments/{assessment_id}/review", json=payload).json()


def render_detections(image_bytes: bytes, detections: list[dict[str, Any]]) -> Image.Image:
    """Overlay API-provided detection evidence without changing the original upload."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    canvas = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for detection in detections:
        box = detection.get("bounding_box_xyxy") or {}
        try:
            coordinates = (float(box["x1"]), float(box["y1"]), float(box["x2"]), float(box["y2"]))
        except (KeyError, TypeError, ValueError):
            continue
        severity = str(detection.get("class_name", "no_detection"))
        color = SEVERITY_COLORS.get(severity, "#38bdf8")
        confidence = float(detection.get("confidence", 0.0))
        label = f"{severity}  {confidence:.0%}"
        canvas.rectangle(coordinates, outline=color, width=max(2, image.width // 300))
        label_box = canvas.textbbox((coordinates[0], coordinates[1]), label, font=font)
        canvas.rectangle(label_box, fill=color)
        canvas.text((coordinates[0], coordinates[1]), label, fill="white", font=font)
    return image


def _severity_label(value: str | None) -> str:
    return str(value or "no_detection").replace("_", " ").title()


def _status_message(explanation: dict[str, Any] | None) -> tuple[str, str] | None:
    if not explanation:
        return None
    state = explanation.get("status")
    if state == "grounded":
        return "success", "Grounded explanation available. Verify each cited source during review."
    if state == "evidence_unavailable":
        return "info", "No approved RAG evidence is available. Consult the applicable source manually."
    if state == "generation_unavailable":
        return "warning", "Gemini is unavailable. The model and retrieved evidence remain available for review."
    return "info", "Explanation status is unavailable."


def _show_notice(kind: str, message: str) -> None:
    getattr(st, kind)(message)


def _load_assessment(client: ClaimSenseClient, assessment_id: str) -> None:
    record = client.get_assessment(assessment_id)
    st.session_state.assessment_id = assessment_id
    st.session_state.assessment = record


def _render_evidence(client: ClaimSenseClient, assessment: dict[str, Any]) -> None:
    st.subheader("Policy/process evidence and explanation")
    retrieval = assessment.get("retrieval", {})
    retrieval_state = retrieval.get("status", "evidence_unavailable")
    if retrieval_state == "retrieved":
        st.success(f"Retrieved {retrieval.get('result_count', 0)} source excerpt(s).")
        for item in assessment.get("retrieved_evidence", []):
            with st.expander(f"{item.get('source_path', 'Unknown source')} · score {float(item.get('score', 0)):.3f}"):
                st.caption(f"Chunk: {item.get('chunk_id', 'unknown')} · Document: {item.get('document_id', 'unknown')}")
                st.write(item.get("text", ""))
    else:
        st.info("No approved RAG evidence is currently available. No policy conclusion has been inferred.")

    explanation = assessment.get("explanation")
    if explanation is None:
        if st.button("Generate grounded explanation", use_container_width=True):
            try:
                with st.spinner("Requesting a grounded reviewer explanation..."):
                    client.generate_explanation(assessment["assessment_id"])
                    _load_assessment(client, assessment["assessment_id"])
                st.rerun()
            except ApiError as exc:
                st.error(str(exc))
        return

    notice = _status_message(explanation)
    if notice:
        _show_notice(*notice)
    st.write(explanation.get("explanation", "No explanation was returned."))
    citations = explanation.get("citations", [])
    if citations:
        st.caption("Citations")
        for citation in citations:
            st.markdown(f"- `{citation.get('source_path', 'unknown')}#{citation.get('chunk_id', 'unknown')}`")


def _render_review(client: ClaimSenseClient, assessment: dict[str, Any]) -> None:
    st.subheader("Human review")
    st.warning("This dashboard records a human reviewer’s action. It does not make insurance, coverage, payout, liability, fraud, cost, or legal decisions.")
    current = assessment.get("human_decision")
    if current:
        st.caption(
            f"Latest review: {current.get('reviewer_id', 'unknown')} · {current.get('action', 'unknown')} · "
            f"{current.get('recorded_at', 'unknown time')}"
        )
    with st.form("human-review-form", clear_on_submit=False):
        reviewer_id = st.text_input("Reviewer identity", value=(current or {}).get("reviewer_id", ""))
        action = st.text_input("Reviewer action", value=(current or {}).get("action", ""), help="Describe the human review action, such as evidence review or escalation.")
        final_decision = st.text_input("Human-recorded final decision", value=(current or {}).get("final_decision", ""))
        current_severity = (current or {}).get("reviewer_severity")
        options = ["No reviewer severity supplied", *SEVERITIES]
        default_index = options.index(current_severity) if current_severity in SEVERITIES else 0
        selected_severity = st.selectbox("Reviewer-edited severity (optional)", options, index=default_index)
        notes = st.text_area("Reviewer notes (optional)", value=(current or {}).get("reviewer_notes", ""), max_chars=4000)
        submitted = st.form_submit_button("Submit human review", use_container_width=True)
    if submitted:
        payload = {
            "reviewer_id": reviewer_id.strip(), "action": action.strip(),
            "final_decision": final_decision.strip(), "reviewer_severity": None if selected_severity.startswith("No ") else selected_severity,
            "reviewer_notes": notes.strip() or None,
        }
        if not all(payload[key] for key in ("reviewer_id", "action", "final_decision")):
            st.error("Reviewer identity, action, and human-recorded final decision are required.")
            return
        try:
            updated = client.submit_review(assessment["assessment_id"], payload)
            st.session_state.assessment = updated
            st.success("Human review recorded. Earlier review entries remain in the audit history.")
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))


def _render_audit(assessment: dict[str, Any]) -> None:
    st.subheader("Assessment and audit history")
    st.caption(f"Assessment ID: `{assessment['assessment_id']}` · Created: {assessment.get('created_at')} · Updated: {assessment.get('updated_at')}")
    for event in reversed(assessment.get("audit_events", [])):
        with st.expander(f"{event.get('at', 'unknown time')} · {event.get('event_type', 'event')}"):
            st.json(event.get("details", {}))
    history = assessment.get("review_history", [])
    if history:
        st.caption("Human review history")
        st.dataframe(history, use_container_width=True, hide_index=True)


def _render_workspace(client: ClaimSenseClient, assessment: dict[str, Any]) -> None:
    analysis = assessment.get("analysis", {})
    severity = analysis.get("provisional_overall_severity", "no_detection")
    st.divider()
    st.subheader(f"Assessment · {_severity_label(severity)}")
    st.warning("AI output is provisional evidence only. A named human reviewer must complete the review.")
    summary, metadata, review = st.columns(3)
    summary.metric("Provisional severity", _severity_label(severity))
    metadata.metric("Detections", len(analysis.get("detections", [])))
    review.metric("Review state", str(assessment.get("status", "awaiting_human_review")).replace("_", " ").title())

    try:
        image_bytes = client.get_image(assessment["assessment_id"])
        original, annotated = st.columns(2)
        with original:
            st.markdown("#### Original upload")
            st.image(image_bytes, use_container_width=True)
        with annotated:
            st.markdown("#### Detection evidence")
            st.image(render_detections(image_bytes, analysis.get("detections", [])), use_container_width=True)
    except (ApiError, OSError) as exc:
        st.error(f"The assessment record is available, but its image cannot be displayed: {exc}")

    if analysis.get("detections"):
        st.dataframe(analysis["detections"], use_container_width=True, hide_index=True)
    else:
        st.info("The model reported no supported damage detections. This does not resolve the claim; human review is still required.")

    evidence_tab, review_tab, history_tab = st.tabs(["Evidence", "Human review", "Audit history"])
    with evidence_tab:
        _render_evidence(client, assessment)
    with review_tab:
        _render_review(client, assessment)
    with history_tab:
        _render_audit(assessment)


def main() -> None:
    st.set_page_config(page_title="ClaimSense Reviewer", page_icon="◆", layout="wide")
    st.markdown("""
        <style>
          .block-container { max-width: 1380px; padding-top: 2rem; }
          [data-testid="stMetric"] { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: .8rem; }
          .stButton > button, .stFormSubmitButton > button { border-radius: 8px; font-weight: 600; }
        </style>
    """, unsafe_allow_html=True)
    st.title("ClaimSense reviewer workspace")
    st.caption("Vehicle-damage evidence review with a required human decision boundary.")

    with st.sidebar:
        st.header("Connection")
        api_url = st.text_input("API URL", value=st.session_state.get("api_url", DEFAULT_API_URL))
        st.session_state.api_url = api_url
        client = ClaimSenseClient(api_url)
        if st.button("Check API connection", use_container_width=True):
            try:
                state = client.health()
                st.success(f"API online · {state.get('decision_boundary', 'human review required')}")
            except ApiError as exc:
                st.error(str(exc))
        st.divider()
        assessment_id = st.text_input("Open assessment ID", value=st.session_state.get("assessment_id", ""))
        if st.button("Load assessment", use_container_width=True):
            if not assessment_id.strip():
                st.error("Enter an assessment ID.")
            else:
                try:
                    _load_assessment(client, assessment_id.strip())
                    st.rerun()
                except ApiError as exc:
                    st.error(str(exc))

    st.subheader("Start an assessment")
    uploaded = st.file_uploader("Vehicle damage image", type=["jpg", "jpeg", "png", "webp"], help="The image is validated and analyzed by the ClaimSense API.")
    if uploaded is not None:
        left, right = st.columns([2, 1])
        with left:
            st.image(uploaded.getvalue(), caption=f"Ready to submit: {uploaded.name}", use_container_width=True)
        with right:
            st.caption("Supported: JPG, JPEG, PNG, WEBP · maximum 10 MB")
            if st.button("Start assessment", type="primary", use_container_width=True):
                try:
                    with st.spinner("Uploading image and generating evidence..."):
                        record = client.create_assessment(uploaded.name, uploaded.getvalue(), uploaded.type)
                    st.session_state.assessment_id = record["assessment_id"]
                    st.session_state.assessment = record
                    st.success("Assessment created. Review the evidence before recording any human action.")
                    st.rerun()
                except ApiError as exc:
                    st.error(str(exc))

    assessment = st.session_state.get("assessment")
    if assessment:
        _render_workspace(client, assessment)
    else:
        st.info("Upload an image or load an existing assessment to begin a reviewer-led workflow.")


if __name__ == "__main__":
    main()
