# ClaimSense severity dataset

## Approved Phase 1 candidate

`PROJECT_AVENGERS_SEVERITY_FINAL.zip`, currently held outside this repository in
the user Downloads folder, is the selected candidate for validation. It is not
copied into the repository during Phase 1. The archive's own metadata identifies
the task as YOLO object detection with three regional severity labels:
`minor`, `moderate`, and `severe`.

The supported prediction is **damage-region localization and severity
classification**. It does not support repair-cost prediction, policy coverage,
claim approval, fraud detection, or payment decisions.

## Provenance and license

The raw source archive identifies Roboflow Universe project `AE / Damage
Severity`, version 1, exported 2 April 2023, under CC BY 4.0. The cleaned
archive declares `Damage_Severity_v1i_yolov8.zip` as its source. Attribution,
license review, and use restrictions must remain with every later dataset copy
and model card. The source URL recorded by the raw archive is:

`https://universe.roboflow.com/ae-43fv6/damage-severity/dataset/1`

## Reproducible validation

Run from the repository root using the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts\validate_dataset.py `
  "C:\Users\HP\Downloads\PROJECT_AVENGERS_SEVERITY_FINAL.zip" `
  --report reports\dataset_validation.json
```

The command reads the ZIP in place and reports its SHA-256 fingerprint, class
metadata, image/label pairing, image readability, bounding-box validity, class
distribution, exact duplicate images, cross-split perceptual-duplicate
candidates, and group-level train/validation/test leakage from
`annotations.csv`.

Bounding boxes are checked with a `1e-5` boundary tolerance to accommodate
rounding from polygon-to-box conversion. Coordinates or boxes materially outside
the normalized image extent remain validation errors.

Cross-split coarse perceptual-hash candidates undergo a local SSIM confirmation
step. Only candidates meeting the cleaned archive's documented conservative
threshold are validation errors; visually related images within the same split
are counted for traceability but do not invalidate evaluation.

`reports/` is generated output and is intentionally ignored by Git once source
control is initialized. A dataset may proceed to training only if the report has
`"is_valid": true`, no unresolved duplicate/leakage findings, and its
provenance/license review remains acceptable for the intended use.

## Candidate inventory

| Candidate | Status | Notes |
|---|---|---|
| `PROJECT_AVENGERS_SEVERITY_FINAL.zip` | Selected | Cleaned 2,598-image severity-detection candidate. |
| Extracted `train`/`valid`/`test` dataset | Baseline only | Original split; do not use for final metrics until leakage is addressed. |
| `PROJECT_AVENGERS_DAMAGE_FINAL.zip` | Separate task | Part localization and damage-type classification, not severity training. |
| `cars_train` / `cars_test` | Not supervised | Images only; labels were not found. |
| `damage.zip` | Pending review | COCO annotations exist but class taxonomy/provenance require separate validation. |
