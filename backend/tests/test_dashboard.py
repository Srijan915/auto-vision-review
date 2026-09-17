from __future__ import annotations

import io
import unittest

from PIL import Image

from src.dashboard import ApiError, ClaimSenseClient, render_detections


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, content: bytes = b"", text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content
        self.text = text

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


class DashboardClientTests(unittest.TestCase):
    def test_client_uses_canonical_assessment_routes(self) -> None:
        session = FakeSession([
            FakeResponse(201, {"assessment_id": "a1"}),
            FakeResponse(200, {"assessment_id": "a1", "status": "awaiting_human_review"}),
            FakeResponse(200, content=b"image-bytes"),
            FakeResponse(200, {"status": "human_review_submitted"}),
        ])
        client = ClaimSenseClient("http://api.example/", session=session)
        self.assertEqual(client.create_assessment("damage.jpg", b"jpeg", "image/jpeg")["assessment_id"], "a1")
        self.assertEqual(client.get_assessment("a1")["assessment_id"], "a1")
        self.assertEqual(client.get_image("a1"), b"image-bytes")
        self.assertEqual(client.submit_review("a1", {"reviewer_id": "r", "action": "review", "final_decision": "complete"})["status"], "human_review_submitted")
        self.assertEqual([call[1] for call in session.calls], [
            "http://api.example/assessments", "http://api.example/assessments/a1",
            "http://api.example/assessments/a1/image", "http://api.example/assessments/a1/review",
        ])
        self.assertIn("image", session.calls[0][2]["files"])

    def test_client_surfaces_backend_error(self) -> None:
        client = ClaimSenseClient("http://api.example", session=FakeSession([FakeResponse(422, {"detail": "invalid image"})]))
        with self.assertRaisesRegex(ApiError, "invalid image"):
            client.create_assessment("bad.jpg", b"bad", "image/jpeg")

    def test_detection_overlay_uses_api_coordinates(self) -> None:
        source = io.BytesIO()
        Image.new("RGB", (32, 24), "white").save(source, format="PNG")
        annotated = render_detections(source.getvalue(), [{
            "class_name": "severe", "confidence": 0.88,
            "bounding_box_xyxy": {"x1": 3, "y1": 4, "x2": 20, "y2": 18},
        }])
        self.assertNotEqual(annotated.getpixel((3, 4)), (255, 255, 255))

