"""Validation utilities for ClaimSense YOLO severity datasets.

The validator deliberately reads ZIP archives in place.  It never extracts,
renames, or changes the source dataset, making the validation result
reproducible and safe to run against the original delivery.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
import cv2
import yaml
from PIL import Image, UnidentifiedImageError


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SPLIT_ALIASES = {"val": "valid", "validation": "valid"}


@dataclass
class ValidationReport:
    """Machine-readable result of a non-destructive dataset validation run."""

    archive: str
    archive_sha256: str
    dataset_root: str
    class_names: list[str]
    task: str
    split_images: dict[str, int] = field(default_factory=dict)
    split_labels: dict[str, int] = field(default_factory=dict)
    annotations_by_class: dict[str, int] = field(default_factory=dict)
    image_dimensions: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    exact_duplicate_groups: list[list[str]] = field(default_factory=list)
    perceptual_duplicate_candidates: list[list[str]] = field(default_factory=list)
    group_leakage: dict[str, list[str]] = field(default_factory=dict)
    metadata_checks: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["is_valid"] = self.is_valid
        return result


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_split(name: str) -> str:
    return SPLIT_ALIASES.get(name.lower(), name.lower())


def _read_yaml(archive: zipfile.ZipFile, path: str) -> dict[str, Any]:
    raw = archive.read(path).decode("utf-8-sig")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError("data.yaml must contain a mapping")
    return data


def _find_dataset_root(archive: zipfile.ZipFile) -> tuple[str, dict[str, Any]]:
    yaml_paths = [name for name in archive.namelist() if name.endswith("data.yaml")]
    if not yaml_paths:
        raise ValueError("Archive does not contain data.yaml")

    candidates: list[tuple[str, dict[str, Any]]] = []
    for yaml_path in yaml_paths:
        try:
            config = _read_yaml(archive, yaml_path)
        except (UnicodeDecodeError, yaml.YAMLError, ValueError):
            continue
        if "names" in config and any(key in config for key in ("train", "val", "valid", "test")):
            root = str(PurePosixPath(yaml_path).parent)
            candidates.append(("" if root == "." else root, config))
    if len(candidates) != 1:
        raise ValueError(f"Expected one usable YOLO data.yaml, found {len(candidates)}")
    return candidates[0]


def _archive_path(root: str, relative: str) -> str:
    return str(PurePosixPath(root, relative)) if root else str(PurePosixPath(relative))


def _dhash(image_bytes: bytes) -> int:
    """Return a small perceptual fingerprint; candidates still require review."""
    with Image.open(io.BytesIO(image_bytes)) as image:
        pixels = np.asarray(image.convert("L").resize((9, 8), Image.Resampling.LANCZOS))
    bits = pixels[:, 1:] >= pixels[:, :-1]
    return int("".join("1" if bit else "0" for bit in bits.flat), 2)


def _hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _local_ssim(left_bytes: bytes, right_bytes: bytes) -> float:
    """Compute local grayscale SSIM for a coarse perceptual-hash candidate."""
    left = cv2.imdecode(np.frombuffer(left_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    right = cv2.imdecode(np.frombuffer(right_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if left is None or right is None or left.shape != right.shape:
        return float("nan")
    left = left.astype(np.float64)
    right = right.astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mean_left = cv2.GaussianBlur(left, (11, 11), 1.5)
    mean_right = cv2.GaussianBlur(right, (11, 11), 1.5)
    variance_left = cv2.GaussianBlur(left * left, (11, 11), 1.5) - mean_left * mean_left
    variance_right = cv2.GaussianBlur(right * right, (11, 11), 1.5) - mean_right * mean_right
    covariance = cv2.GaussianBlur(left * right, (11, 11), 1.5) - mean_left * mean_right
    score = ((2 * mean_left * mean_right + c1) * (2 * covariance + c2)) / (
        (mean_left * mean_left + mean_right * mean_right + c1) * (variance_left + variance_right + c2)
    )
    return float(score.mean())


def _dimensions_summary(dimensions: list[tuple[int, int]]) -> dict[str, Any]:
    widths = [width for width, _ in dimensions]
    heights = [height for _, height in dimensions]
    if not dimensions:
        return {}
    return {
        "count": len(dimensions),
        "unique": len(set(dimensions)),
        "most_common": [list(size) for size, _ in Counter(dimensions).most_common(5)],
        "width_range": [min(widths), max(widths)],
        "height_range": [min(heights), max(heights)],
    }


def validate_yolo_archive(
    archive_path: str | Path,
    *,
    perceptual_distance: int = 3,
    box_tolerance: float = 1e-5,
) -> ValidationReport:
    """Validate a YOLO detection archive and return a structured report.

    This supports normalized YOLO bounding boxes (class, cx, cy, width, height).
    Exact image duplication is an error; perceptual matches are warnings because
    visually similar legitimate photos can share a fingerprint.
    """
    source = Path(archive_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    with zipfile.ZipFile(source) as archive:
        root, config = _find_dataset_root(archive)
        names_value = config.get("names", [])
        class_names = list(names_value.values()) if isinstance(names_value, dict) else list(names_value)
        report = ValidationReport(
            archive=str(source),
            archive_sha256=sha256_file(source),
            dataset_root=root,
            class_names=[str(name) for name in class_names],
            task="object detection: localize vehicle-damage regions and classify their severity",
        )
        declared_count = config.get("nc")
        if declared_count != len(class_names):
            report.errors.append(f"data.yaml nc={declared_count} but names has {len(class_names)} classes")

        image_by_split: dict[str, list[str]] = {}
        label_by_split: dict[str, set[str]] = {}
        for yaml_split, relative in config.items():
            split = _normalise_split(str(yaml_split))
            if split not in {"train", "valid", "test"} or not isinstance(relative, str):
                continue
            directory = _archive_path(root, relative).rstrip("/")
            image_paths = [
                name for name in archive.namelist()
                if name.startswith(directory + "/") and PurePosixPath(name).suffix.lower() in IMAGE_SUFFIXES
            ]
            label_directory = directory.rsplit("/", 1)[0] + "/labels"
            label_paths = {
                name for name in archive.namelist()
                if name.startswith(label_directory + "/") and PurePosixPath(name).suffix.lower() == ".txt"
            }
            image_by_split[split] = image_paths
            label_by_split[split] = label_paths
            report.split_images[split] = len(image_paths)
            report.split_labels[split] = len(label_paths)

        required_splits = {"train", "valid", "test"}
        missing_splits = required_splits.difference(image_by_split)
        if missing_splits:
            report.errors.append(f"data.yaml is missing required split(s): {sorted(missing_splits)}")

        annotation_counts: Counter[str] = Counter()
        dimensions: list[tuple[int, int]] = []
        exact_hashes: dict[str, list[str]] = defaultdict(list)
        perceptual_hashes: list[tuple[int, str]] = []

        for split, image_paths in image_by_split.items():
            expected_labels = label_by_split[split]
            for image_path in image_paths:
                image_name = PurePosixPath(image_path)
                label_path = str(image_name.parent.parent / "labels" / f"{image_name.stem}.txt")
                if label_path not in expected_labels:
                    report.errors.append(f"Missing label for {image_path}")
                    continue

                image_bytes = archive.read(image_path)
                try:
                    with Image.open(io.BytesIO(image_bytes)) as image:
                        image.verify()
                    with Image.open(io.BytesIO(image_bytes)) as image:
                        dimensions.append(image.size)
                except (UnidentifiedImageError, OSError) as exc:
                    report.errors.append(f"Unreadable image {image_path}: {exc}")
                    continue
                exact_hashes[hashlib.sha256(image_bytes).hexdigest()].append(image_path)
                perceptual_hashes.append((_dhash(image_bytes), image_path))

                text = archive.read(label_path).decode("utf-8-sig")
                if not text.strip():
                    report.errors.append(f"Empty annotation file {label_path}")
                for line_number, line in enumerate(text.splitlines(), start=1):
                    fields = line.split()
                    if len(fields) != 5:
                        report.errors.append(f"{label_path}:{line_number} must have 5 YOLO fields")
                        continue
                    try:
                        class_id = int(fields[0])
                        cx, cy, width, height = (float(value) for value in fields[1:])
                    except ValueError:
                        report.errors.append(f"{label_path}:{line_number} has non-numeric values")
                        continue
                    if not 0 <= class_id < len(class_names):
                        report.errors.append(f"{label_path}:{line_number} has invalid class id {class_id}")
                    if not all(math.isfinite(value) for value in (cx, cy, width, height)):
                        report.errors.append(f"{label_path}:{line_number} has non-finite coordinates")
                    elif (
                        width <= 0
                        or height <= 0
                        or cx - width / 2 < -box_tolerance
                        or cy - height / 2 < -box_tolerance
                        or cx + width / 2 > 1 + box_tolerance
                        or cy + height / 2 > 1 + box_tolerance
                    ):
                        report.errors.append(f"{label_path}:{line_number} has out-of-bounds bounding box")
                    else:
                        annotation_counts[str(class_id)] += 1

            image_stems = {PurePosixPath(path).stem for path in image_paths}
            label_stems = {PurePosixPath(path).stem for path in expected_labels}
            for orphan in sorted(label_stems.difference(image_stems)):
                report.errors.append(f"Orphan label in {split}: {orphan}.txt")

        report.annotations_by_class = {
            class_names[int(class_id)]: count for class_id, count in sorted(annotation_counts.items(), key=lambda item: int(item[0]))
        }
        report.image_dimensions = _dimensions_summary(dimensions)
        report.exact_duplicate_groups = [paths for paths in exact_hashes.values() if len(paths) > 1]
        if report.exact_duplicate_groups:
            report.errors.append(f"Found {len(report.exact_duplicate_groups)} exact duplicate image group(s)")

        # Compare all cross-split perceptual fingerprints. This is deliberately
        # stricter than checking only a hash bucket: cross-split leakage is the
        # risk that would invalidate held-out evaluation.
        within_split_candidates = 0
        cross_split_candidates: list[tuple[str, str, int]] = []
        for index, (fingerprint, path) in enumerate(perceptual_hashes):
            split = _normalise_split(PurePosixPath(path).parts[-3])
            for other_fingerprint, other_path in perceptual_hashes[index + 1 :]:
                distance = _hamming_distance(fingerprint, other_fingerprint)
                if distance > perceptual_distance:
                    continue
                other_split = _normalise_split(PurePosixPath(other_path).parts[-3])
                if split == other_split:
                    within_split_candidates += 1
                else:
                    cross_split_candidates.append((path, other_path, distance))

        strong_candidates: list[list[str]] = []
        cross_scores: list[float] = []
        for left, right, distance in cross_split_candidates:
            score = _local_ssim(archive.read(left), archive.read(right))
            cross_scores.append(score)
            # Mirrors the cleaned archive's documented conservative rule.
            threshold = 0.90 if distance <= 1 else 0.95
            if math.isfinite(score) and score >= threshold:
                strong_candidates.append([left, right])
        report.perceptual_duplicate_candidates = strong_candidates
        report.metadata_checks["within_split_perceptual_candidate_pairs"] = within_split_candidates
        report.metadata_checks["cross_split_perceptual_candidate_pairs"] = len(cross_split_candidates)
        report.metadata_checks["strong_cross_split_near_duplicate_pairs"] = len(strong_candidates)
        report.metadata_checks["highest_cross_split_local_ssim"] = round(max(cross_scores), 4) if cross_scores else None
        if strong_candidates:
            report.errors.append(f"Found {len(strong_candidates)} strong cross-split near-duplicate pair(s)")

        annotations_path = _archive_path(root, "annotations.csv")
        report.metadata_checks["annotations_csv_present"] = annotations_path in archive.namelist()
        if annotations_path in archive.namelist():
            rows = csv.DictReader(io.TextIOWrapper(archive.open(annotations_path), encoding="utf-8-sig"))
            group_splits: dict[str, set[str]] = defaultdict(set)
            metadata_annotations = 0
            for row in rows:
                metadata_annotations += 1
                group_id, split = row.get("group_id"), row.get("split")
                if group_id and split:
                    group_splits[group_id].add(_normalise_split(split))
            report.metadata_checks["annotations_csv_rows"] = metadata_annotations
            report.group_leakage = {key: sorted(value) for key, value in group_splits.items() if len(value) > 1}
            if report.group_leakage:
                report.errors.append(f"Found {len(report.group_leakage)} group(s) crossing data splits")

        cleaning_path = _archive_path(root, "CLEANING_REPORT.json")
        if cleaning_path in archive.namelist():
            cleaning = json.loads(archive.read(cleaning_path).decode("utf-8-sig"))
            report.metadata_checks["cleaning_report_present"] = True
            expected_images = cleaning.get("final_images")
            actual_images = sum(report.split_images.values())
            report.metadata_checks["cleaning_report_final_images"] = expected_images
            if expected_images is not None and expected_images != actual_images:
                report.errors.append(f"Cleaning report expects {expected_images} images; found {actual_images}")
        else:
            report.warnings.append("CLEANING_REPORT.json is absent; split-leakage provenance is incomplete")

    return report


def write_report(report: ValidationReport, output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return destination
