"""Transparent detection-level error analysis for ClaimSense Phase 2."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from ultralytics import YOLO


def _iou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    if len(boxes) == 0:
        return np.empty(0)
    intersection_left_top = np.maximum(box[:2], boxes[:, :2])
    intersection_right_bottom = np.minimum(box[2:], boxes[:, 2:])
    intersection = np.clip(intersection_right_bottom - intersection_left_top, 0, None)
    intersection_area = intersection[:, 0] * intersection[:, 1]
    box_area = max(0.0, (box[2] - box[0]) * (box[3] - box[1]))
    boxes_area = np.clip(boxes[:, 2] - boxes[:, 0], 0, None) * np.clip(boxes[:, 3] - boxes[:, 1], 0, None)
    return intersection_area / np.maximum(box_area + boxes_area - intersection_area, 1e-12)


def _ground_truth(label_path: Path, width: int, height: int) -> list[tuple[int, np.ndarray]]:
    targets: list[tuple[int, np.ndarray]] = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        class_id, cx, cy, box_width, box_height = map(float, line.split())
        x1, y1 = (cx - box_width / 2) * width, (cy - box_height / 2) * height
        x2, y2 = (cx + box_width / 2) * width, (cy + box_height / 2) * height
        targets.append((int(class_id), np.array([x1, y1, x2, y2], dtype=float)))
    return targets


def _split_paths(data_yaml: Path, split: str) -> tuple[list[Path], list[str]]:
    config = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    relative = config["val" if split == "valid" else split]
    image_dir = data_yaml.parent / relative
    images = sorted(path for path in image_dir.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    names = list(config["names"].values()) if isinstance(config["names"], dict) else list(config["names"])
    return images, [str(name) for name in names]


def detection_analysis(checkpoint: str | Path, data_yaml: str | Path, split: str, output_dir: str | Path, confidence: float = 0.001) -> dict[str, Any]:
    """Match predictions to labels class-wise at IoU 0.50 and persist audit rows."""
    data_yaml, output_dir = Path(data_yaml), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    images, names = _split_paths(data_yaml, split)
    model = YOLO(str(checkpoint))
    rows: list[dict[str, Any]] = []
    for image_path, result in zip(images, model.predict([str(path) for path in images], imgsz=640, conf=confidence, device="cpu", verbose=False, stream=False)):
        height, width = result.orig_shape
        label_path = image_path.parent.parent / "labels" / f"{image_path.stem}.txt"
        targets = _ground_truth(label_path, width, height)
        unmatched = set(range(len(targets)))
        boxes = result.boxes
        predictions = [] if boxes is None else sorted(
            zip(boxes.cls.cpu().numpy().astype(int), boxes.conf.cpu().numpy(), boxes.xyxy.cpu().numpy()),
            key=lambda item: float(item[1]), reverse=True,
        )
        for class_id, score, box in predictions:
            candidates = [index for index in unmatched if targets[index][0] == class_id]
            overlaps = _iou(box, np.asarray([targets[index][1] for index in candidates])) if candidates else np.empty(0)
            if len(overlaps) and float(overlaps.max()) >= 0.5:
                target_index = candidates[int(overlaps.argmax())]
                unmatched.remove(target_index)
                outcome, matched_iou = "true_positive", float(overlaps.max())
            else:
                outcome, matched_iou = "false_positive", None
            rows.append({"image": str(image_path), "split": split, "class_id": class_id, "class_name": names[class_id], "confidence": float(score), "outcome": outcome, "iou": matched_iou})
        for target_index in unmatched:
            class_id, _ = targets[target_index]
            rows.append({"image": str(image_path), "split": split, "class_id": class_id, "class_name": names[class_id], "confidence": 0.0, "outcome": "false_negative", "iou": None})

    with (output_dir / "detection_rows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "split", "class_id", "class_name", "confidence", "outcome", "iou"])
        writer.writeheader(); writer.writerows(rows)
    return {"split": split, "class_names": names, "rows": rows, "output_dir": str(output_dir)}


def select_review_threshold(validation_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Select a data-derived review threshold: maximum detection F1 at IoU 0.50."""
    candidates = sorted({round(float(row["confidence"]), 3) for row in validation_rows if row["outcome"] != "false_negative"})
    best = {"threshold": 0.0, "precision": 0.0, "recall": 0.0, "f1": -1.0}
    total_ground_truth = sum(row["outcome"] in {"true_positive", "false_negative"} for row in validation_rows)
    for threshold in candidates:
        true_positive = sum(row["outcome"] == "true_positive" and row["confidence"] >= threshold for row in validation_rows)
        false_positive = sum(row["outcome"] == "false_positive" and row["confidence"] >= threshold for row in validation_rows)
        false_negative = total_ground_truth - true_positive
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / total_ground_truth if total_ground_truth else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if f1 > best["f1"]:
            best = {"threshold": threshold, "precision": precision, "recall": recall, "f1": f1}
    return best


def summarise_analysis(analysis: dict[str, Any], threshold: float) -> dict[str, Any]:
    rows, names = analysis["rows"], analysis["class_names"]
    per_class: list[dict[str, Any]] = []
    for class_id, name in enumerate(names):
        class_rows = [row for row in rows if row["class_id"] == class_id]
        tp = sum(row["outcome"] == "true_positive" and row["confidence"] >= threshold for row in class_rows)
        fp = sum(row["outcome"] == "false_positive" and row["confidence"] >= threshold for row in class_rows)
        fn = sum(row["outcome"] == "false_negative" or (row["outcome"] == "true_positive" and row["confidence"] < threshold) for row in class_rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        per_class.append({"class_name": name, "tp": tp, "fp": fp, "fn": fn, "precision_iou50": precision, "recall_iou50": recall})
    confidence_bins = Counter()
    for row in rows:
        if row["outcome"] != "false_negative":
            confidence_bins[f"{int(row['confidence'] * 10) / 10:.1f}-{min(1.0, int(row['confidence'] * 10) / 10 + 0.1):.1f}"] += 1
    examples = {
        "correct": [row["image"] for row in rows if row["outcome"] == "true_positive"][:10],
        "incorrect": [row["image"] for row in rows if row["outcome"] in {"false_positive", "false_negative"}][:10],
        "low_confidence": [row["image"] for row in rows if 0 < row["confidence"] < threshold][:10],
    }
    result = {"review_threshold": threshold, "per_class_iou50": per_class, "confidence_distribution": dict(confidence_bins), "examples": examples}
    Path(analysis["output_dir"]).joinpath("analysis_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
