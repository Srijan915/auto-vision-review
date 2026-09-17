"""ClaimSense Phase 2 entry point: validate, prepare, train, then test once."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.damage_model import SeverityTrainingConfig, evaluate_on_test_set, preserve_best_checkpoint, train_severity_detector
from src.model_evaluation import detection_analysis, select_review_threshold, summarise_analysis
from src.preprocessing import materialize_validated_yolo_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Train and evaluate ClaimSense severity detector.")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/training/severity_yolov8n_cpu.yaml"))
    parser.add_argument("--run-id", default=None)
    arguments = parser.parse_args()
    run_id = arguments.run_id or "severity-yolov8n-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    prepared = materialize_validated_yolo_dataset(arguments.archive, PROJECT_ROOT / "data" / "processed")
    if not prepared.validation.is_valid:
        raise RuntimeError("Final validation gate failed")
    config = SeverityTrainingConfig.from_yaml(PROJECT_ROOT / arguments.config)
    training_dir = train_severity_detector(config, prepared.data_yaml, PROJECT_ROOT / "artifacts" / "training" / "severity", run_id)
    validation_analysis = detection_analysis(training_dir / "weights" / "best.pt", prepared.data_yaml, "valid", PROJECT_ROOT / "artifacts" / "analysis" / "validation" / run_id)
    threshold = select_review_threshold(validation_analysis["rows"])
    evaluation = evaluate_on_test_set(training_dir / "weights" / "best.pt", prepared.data_yaml, PROJECT_ROOT / "artifacts" / "evaluation" / "severity", run_id)
    test_analysis = detection_analysis(training_dir / "weights" / "best.pt", prepared.data_yaml, "test", PROJECT_ROOT / "artifacts" / "analysis" / "test" / run_id)
    error_analysis = summarise_analysis(test_analysis, threshold["threshold"])
    checkpoint = preserve_best_checkpoint(training_dir, PROJECT_ROOT / "models" / "severity", run_id, {
        "run_id": run_id,
        "dataset_archive_sha256": prepared.validation.archive_sha256,
        "classes": prepared.validation.class_names,
        "training_config": json.loads((training_dir / "training_config.json").read_text(encoding="utf-8")),
        "test_evaluation": evaluation,
        "validation_threshold_selection": threshold,
        "test_error_analysis": error_analysis,
        "limitations": "Damage-region severity decision support only; not coverage, payout, liability, fraud, or repair-cost prediction.",
    })
    print(json.dumps({"run_id": run_id, "training_dir": str(training_dir), "checkpoint": str(checkpoint), "evaluation": evaluation}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
