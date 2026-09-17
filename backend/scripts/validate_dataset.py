"""Run ClaimSense's non-destructive dataset validation from the command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Support direct execution from the repository root as documented below.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dataset_validation import validate_yolo_archive, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a YOLO severity dataset ZIP without extracting it.")
    parser.add_argument("archive", type=Path, help="Path to the source ZIP archive")
    parser.add_argument("--report", type=Path, default=Path("reports/dataset_validation.json"))
    arguments = parser.parse_args()

    report = validate_yolo_archive(arguments.archive)
    write_report(report, arguments.report)
    print(f"Validation report: {arguments.report}")
    print(f"Dataset valid: {report.is_valid}")
    print(f"Classes: {', '.join(report.class_names)}")
    print(f"Images by split: {report.split_images}")
    print(f"Annotations by class: {report.annotations_by_class}")
    print(f"Errors: {len(report.errors)}; warnings: {len(report.warnings)}")
    return 0 if report.is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
