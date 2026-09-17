# Phase 1 validation result

## Decision

`PROJECT_AVENGERS_SEVERITY_FINAL.zip` passed ClaimSense dataset validation and
is eligible to enter Phase 2 training **after this source archive is explicitly
made available to the training workflow**. Phase 1 did not extract or copy it
into this repository.

## Reproducible identity

- Archive: `PROJECT_AVENGERS_SEVERITY_FINAL.zip`
- SHA-256: `8949350df4fa9415b950ac594a50d2a164fd1fd4a7a9f441d7e514879ad127f7`
- Dataset root: `PROJECT_AVENGERS_SEVERITY_FINAL`
- Validation command: documented in [dataset.md](dataset.md)

## Verified structure

| Split | Images | Label files |
|---|---:|---:|
| Train | 1,832 | 1,832 |
| Validation | 382 | 382 |
| Test | 384 | 384 |
| Total | 2,598 | 2,598 |

All images decoded successfully and are 640 × 640 pixels. All 4,636 YOLO
annotations have five fields, valid class IDs, finite normalized coordinates,
and non-zero dimensions. A `1e-5` tolerance covers only polygon-conversion
rounding at image boundaries.

## Target derived from the data

This is an object-detection task. Each annotation is a localized damage region
with one severity class:

| Class | Annotation count | Share |
|---|---:|---:|
| minor | 1,494 | 32.2% |
| moderate | 2,466 | 53.2% |
| severe | 676 | 14.6% |

The model may predict damage boxes, a severity label, and confidence. It must
not be represented as predicting coverage, cost, payment, fraud, liability, or
claim approval.

## Leakage and duplicate checks

- Exact duplicate image groups: 0
- `annotations.csv` rows: 4,636
- Metadata group IDs crossing train/validation/test: 0
- Coarse cross-split perceptual candidates: 11
- Strong cross-split near duplicates after local SSIM confirmation: 0
- Highest cross-split local SSIM candidate: 0.8786

The archive's cleaning report records 896 source groups and prior
near-duplicate controls. The validator independently confirms that no candidate
meets its documented strong-match threshold. Related images inside a single
split are retained and counted for traceability; they do not contaminate held-out
evaluation.

## Provenance and use conditions

The archive identifies `Damage_Severity_v1i_yolov8.zip` as its source. The raw
source metadata identifies Roboflow Universe's AE / Damage Severity dataset,
version 1, exported 2 April 2023, under CC BY 4.0. Preserve attribution and
review whether this license and the source imagery are appropriate for the
intended deployment before release.

## Phase 2 gate

Before training, use this exact archive fingerprint, keep its test split
untouched, use validation metrics for model selection, and record model
configuration, hardware, seed, code version, and evaluation metrics in the
model card.
