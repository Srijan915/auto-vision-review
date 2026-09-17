"""Training, evaluation, and inference helpers for ClaimSense severity detection."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml
from ultralytics import YOLO

from src.preprocessing import validate_inference_image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_RELATIVE_PATH = Path("models/severity/severity-yolov8n-20260906T185437Z/best.pt")
SUPPORTED_SEVERITIES = ("minor", "moderate", "severe")
SEVERITY_RANK = {severity: index for index, severity in enumerate(SUPPORTED_SEVERITIES)}


@dataclass(frozen=True)
class SeverityInferenceSettings:
    """Runtime settings. Low-confidence detections remain in the response."""

    model_path: Path
    device: str = "cpu"
    imgsz: int = 640
    minimum_detection_confidence: float = 0.001
    human_review_confidence: float = 0.25

    def __post_init__(self) -> None:
        for value in (self.minimum_detection_confidence, self.human_review_confidence):
            if not 0.0 <= value <= 1.0:
                raise ValueError("Confidence thresholds must be between 0 and 1")


def resolve_severity_model_path(model_path: str | Path | None = None) -> Path:
    """Resolve the checkpoint from an explicit path, env var, or project default."""
    candidate = model_path or os.getenv("CLAIMSENSE_SEVERITY_MODEL_PATH") or PROJECT_ROOT / DEFAULT_MODEL_RELATIVE_PATH
    resolved = Path(candidate).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"ClaimSense severity checkpoint was not found: {resolved}")
    return resolved


def load_inference_settings(config_path: str | Path = PROJECT_ROOT / "configs/model_inference.yaml") -> SeverityInferenceSettings:
    """Load documented runtime settings, resolving a relative checkpoint safely."""
    path = Path(config_path).resolve()
    values = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError("Model inference configuration must be a mapping")
    model_value = Path(values.pop("model_path"))
    if not model_value.is_absolute():
        model_value = PROJECT_ROOT / model_value
    return SeverityInferenceSettings(model_path=resolve_severity_model_path(model_value), **values)


def aggregate_severity(detections: list[Mapping[str, Any]]) -> str:
    """Return the highest detected supported severity, or no_detection."""
    severities = [str(detection["class_name"]) for detection in detections if str(detection.get("class_name")) in SEVERITY_RANK]
    return max(severities, key=SEVERITY_RANK.__getitem__) if severities else "no_detection"


class SeverityDetector:
    """CPU-ready, structured inference facade over the recovered YOLOv8n model.

    This class produces AI evidence only. It deliberately contains no policy,
    coverage, payout, liability, fraud, cost, or approval logic.
    """

    def __init__(self, settings: SeverityInferenceSettings | None = None, model: YOLO | None = None) -> None:
        self.settings = settings or load_inference_settings()
        self.model_path = resolve_severity_model_path(self.settings.model_path)
        self.model = model or YOLO(str(self.model_path))
        names = self.model.names
        self.class_names = tuple(str(names[index]) for index in sorted(names))
        if self.class_names != SUPPORTED_SEVERITIES:
            raise ValueError(f"Unexpected model classes {self.class_names}; expected {SUPPORTED_SEVERITIES}")

    def predict(self, image_path: str | Path) -> dict[str, Any]:
        image = validate_inference_image(image_path)
        result = self.model.predict(
            source=str(image.path), imgsz=self.settings.imgsz, device=self.settings.device,
            conf=self.settings.minimum_detection_confidence, verbose=False, save=False,
        )[0]
        detections: list[dict[str, Any]] = []
        boxes = result.boxes
        if boxes is not None:
            for class_id, confidence, xyxy in zip(
                boxes.cls.cpu().numpy().astype(int), boxes.conf.cpu().numpy(), boxes.xyxy.cpu().numpy()
            ):
                class_name = self.class_names[int(class_id)]
                detections.append({
                    "class_id": int(class_id),
                    "class_name": class_name,
                    "confidence": float(confidence),
                    "bounding_box_xyxy": {
                        "x1": float(xyxy[0]), "y1": float(xyxy[1]),
                        "x2": float(xyxy[2]), "y2": float(xyxy[3]),
                    },
                    "requires_human_review": bool(confidence < self.settings.human_review_confidence),
                })
        detections.sort(key=lambda detection: detection["confidence"], reverse=True)
        overall = aggregate_severity(detections)
        return {
            "model": {
                "identifier": self.model_path.parent.name,
                "architecture": "YOLOv8n",
                "checkpoint": str(self.model_path),
                "classes": list(self.class_names),
                "image_size": self.settings.imgsz,
            },
            "image": {"path": str(image.path), "width": image.width, "height": image.height, "format": image.format},
            "detections": detections,
            "provisional_overall_severity": overall,
            "review": {
                "human_decision_required": True,
                "review_reason": "no_damage_detection" if overall == "no_detection" else (
                    "low_confidence_detection" if any(item["requires_human_review"] for item in detections) else "human_review_required"
                ),
                "human_review_confidence_threshold": self.settings.human_review_confidence,
                "minimum_detection_confidence": self.settings.minimum_detection_confidence,
            },
            "processing": {"device": self.settings.device, "raw_detection_count": len(detections)},
        }


@dataclass(frozen=True)
class SeverityTrainingConfig:
    model: str
    epochs: int
    patience: int
    batch: int
    imgsz: int
    device: str
    workers: int
    seed: int
    optimizer: str
    lr0: float
    lrf: float
    weight_decay: float
    cos_lr: bool
    deterministic: bool
    pretrained: bool
    augment: dict[str, float]

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SeverityTrainingConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(**data)


def train_severity_detector(
    config: SeverityTrainingConfig,
    data_yaml: str | Path,
    output_root: str | Path,
    run_id: str,
) -> Path:
    """Train YOLO using validation data for selection; never evaluates test here."""
    output_root = Path(output_root)
    run_dir = output_root / run_id
    if run_dir.exists():
        raise FileExistsError(f"Run directory already exists: {run_dir}")
    model = YOLO(config.model)
    arguments: dict[str, Any] = {
        "data": str(Path(data_yaml).resolve()),
        "epochs": config.epochs,
        "patience": config.patience,
        "batch": config.batch,
        "imgsz": config.imgsz,
        "device": config.device,
        "workers": config.workers,
        "seed": config.seed,
        "optimizer": config.optimizer,
        "lr0": config.lr0,
        "lrf": config.lrf,
        "weight_decay": config.weight_decay,
        "cos_lr": config.cos_lr,
        "deterministic": config.deterministic,
        "pretrained": config.pretrained,
        "project": str(output_root),
        "name": run_id,
        "exist_ok": False,
        "plots": True,
        "val": True,
        **config.augment,
    }
    model.train(**arguments)
    if not (run_dir / "weights" / "best.pt").is_file():
        raise RuntimeError("Training completed without a best.pt validation checkpoint")
    (run_dir / "training_config.json").write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    return run_dir


def evaluate_on_test_set(best_checkpoint: str | Path, data_yaml: str | Path, output_root: str | Path, run_id: str) -> dict[str, Any]:
    """Run exactly one held-out test evaluation and save Ultralytics plots/metrics."""
    output_root = Path(output_root)
    evaluation_dir = output_root / run_id
    if evaluation_dir.exists():
        raise FileExistsError(f"Evaluation directory already exists: {evaluation_dir}")
    model = YOLO(str(best_checkpoint))
    metrics = model.val(
        data=str(Path(data_yaml).resolve()), split="test", imgsz=640, batch=4,
        device="cpu", workers=0, project=str(output_root), name=run_id,
        exist_ok=False, plots=True, verbose=False,
    )
    names = metrics.names
    per_class = []
    for index, name in names.items():
        per_class.append({
            "class_id": int(index), "class_name": str(name),
            "precision": float(metrics.box.p[index]), "recall": float(metrics.box.r[index]),
            "map50": float(metrics.box.ap50[index]), "map50_95": float(metrics.box.ap[index]),
        })
    summary = {
        "checkpoint": str(Path(best_checkpoint).resolve()),
        "metrics": {key: float(value) for key, value in metrics.results_dict.items()},
        "per_class": per_class,
    }
    (evaluation_dir / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def preserve_best_checkpoint(training_dir: str | Path, model_root: str | Path, run_id: str, metadata: dict[str, Any]) -> Path:
    """Copy best validation checkpoint into an immutable, uniquely named model directory."""
    destination = Path(model_root) / run_id
    if destination.exists():
        raise FileExistsError(f"Model destination already exists: {destination}")
    destination.mkdir(parents=True)
    source = Path(training_dir) / "weights" / "best.pt"
    checkpoint = destination / "best.pt"
    shutil.copy2(source, checkpoint)
    (destination / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return checkpoint


def load_severity_detector(checkpoint: str | Path) -> YOLO:
    return YOLO(str(checkpoint))
