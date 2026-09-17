from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

from src.dataset_validation import validate_yolo_archive


def image_bytes(offset: int) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (32, 32), "white")
    ImageDraw.Draw(image).rectangle((offset, 0, offset + 5, 31), fill="black")
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def build_archive(path: Path, *, invalid_box: bool = False) -> None:
    config = "train: train/images\nval: valid/images\ntest: test/images\nnc: 3\nnames: [minor, moderate, severe]\n"
    annotation_rows = "image,split,group_id\ntrain/images/a.jpg,train,G1\nvalid/images/b.jpg,valid,G2\ntest/images/c.jpg,test,G3\n"
    box = "0 0.5 0.5 1.5 0.5" if invalid_box else "0 0.5 0.5 0.5 0.5"
    with zipfile.ZipFile(path, "w") as archive:
        root = "dataset"
        archive.writestr(f"{root}/data.yaml", config)
        archive.writestr(f"{root}/annotations.csv", annotation_rows)
        archive.writestr(f"{root}/CLEANING_REPORT.json", json.dumps({"final_images": 3}))
        for split, name, offset in (("train", "a", 0), ("valid", "b", 12), ("test", "c", 24)):
            archive.writestr(f"{root}/{split}/images/{name}.jpg", image_bytes(offset))
            archive.writestr(f"{root}/{split}/labels/{name}.txt", box)


class DatasetValidationTests(unittest.TestCase):
    def test_valid_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "dataset.zip"
            build_archive(archive)
            report = validate_yolo_archive(archive)
        self.assertTrue(report.is_valid, report.errors)
        self.assertEqual(report.class_names, ["minor", "moderate", "severe"])
        self.assertEqual(report.split_images, {"train": 1, "valid": 1, "test": 1})

    def test_invalid_box_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "dataset.zip"
            build_archive(archive, invalid_box=True)
            report = validate_yolo_archive(archive)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("out-of-bounds" in error for error in report.errors))
