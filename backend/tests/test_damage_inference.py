from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.damage_model import (
    SUPPORTED_SEVERITIES, SeverityDetector, SeverityInferenceSettings,
    aggregate_severity, load_inference_settings, resolve_severity_model_path,
)
from src.preprocessing import InvalidImageError, validate_inference_image


class FakeBoxes:
    def __init__(self) -> None:
        import numpy as np
        import torch
        self.cls = torch.tensor([0, 2])
        self.conf = torch.tensor([0.9, 0.1])
        self.xyxy = torch.tensor([[1, 2, 30, 40], [5, 6, 50, 60]], dtype=torch.float32)


class FakeResult:
    boxes = FakeBoxes()


class FakeModel:
    names = {0: "minor", 1: "moderate", 2: "severe"}
    def predict(self, **_: object) -> list[FakeResult]:
        return [FakeResult()]


class EmptyResult:
    boxes = None


class EmptyFakeModel(FakeModel):
    def predict(self, **_: object) -> list[EmptyResult]:
        return [EmptyResult()]


class DamageInferenceTests(unittest.TestCase):
    def test_model_path_resolution(self) -> None:
        path = resolve_severity_model_path()
        self.assertTrue(path.is_file())
        self.assertEqual(path.name, "best.pt")
        self.assertEqual(load_inference_settings().model_path, path)

    def test_real_model_loads_on_cpu(self) -> None:
        detector = SeverityDetector()
        self.assertEqual(detector.class_names, SUPPORTED_SEVERITIES)

    def test_aggregation_and_no_detection(self) -> None:
        self.assertEqual(aggregate_severity([]), "no_detection")
        self.assertEqual(aggregate_severity([{"class_name": "minor"}, {"class_name": "severe"}]), "severe")

    def test_structured_response_and_review_flags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "vehicle.jpg"
            Image.new("RGB", (100, 80), "white").save(image)
            detector = SeverityDetector(
                SeverityInferenceSettings(model_path=resolve_severity_model_path(), human_review_confidence=0.25),
                model=FakeModel(),
            )
            result = detector.predict(image)
        self.assertEqual(result["model"]["classes"], list(SUPPORTED_SEVERITIES))
        self.assertEqual(result["image"]["width"], 100)
        self.assertEqual(result["provisional_overall_severity"], "severe")
        self.assertTrue(result["detections"][1]["requires_human_review"])
        self.assertTrue(result["review"]["human_decision_required"])

    def test_no_detection_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "vehicle.png"
            Image.new("RGB", (20, 20), "white").save(image)
            detector = SeverityDetector(SeverityInferenceSettings(model_path=resolve_severity_model_path()), model=EmptyFakeModel())
            result = detector.predict(image)
        self.assertEqual(result["detections"], [])
        self.assertEqual(result["provisional_overall_severity"], "no_detection")
        self.assertEqual(result["review"]["review_reason"], "no_damage_detection")

    def test_invalid_image_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-an-image.txt"
            path.write_text("not an image", encoding="utf-8")
            with self.assertRaises(InvalidImageError):
                validate_inference_image(path)

    def test_corrupt_supported_image_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrupt.jpg"
            path.write_bytes(b"not a JPEG payload")
            with self.assertRaises(InvalidImageError):
                validate_inference_image(path)
