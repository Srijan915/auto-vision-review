# ClaimSense severity-model inference

## Recovered model

The inference layer loads:

`models/severity/severity-yolov8n-20260906T185437Z/best.pt`

It is a YOLOv8n object detector trained at 640 pixels for 60 epochs with seed
42. Its only classes are `minor`, `moderate`, and `severe`. Training data
validation and provenance are documented in [dataset.md](dataset.md) and
[phase-1-validation.md](phase-1-validation.md).

Held-out results already recorded for this checkpoint are mAP@50 `0.188` and
mAP@50:95 `0.096`; see the saved evaluation artifact. These results do **not**
support production-ready or autonomous use.

## Calling the inference layer

```python
from src.damage_model import SeverityDetector

assessment = SeverityDetector().predict("vehicle_photo.jpg")
```

The structured response contains raw bounding boxes, classes, confidences,
image metadata, a deterministic provisional severity, and review flags. The
provisional severity is the highest detected severity: `severe > moderate >
minor`. No valid detection returns `no_detection`; ClaimSense never guesses.

`configs/model_inference.yaml` documents default CPU settings. The checkpoint
can also be supplied explicitly or via `CLAIMSENSE_SEVERITY_MODEL_PATH`.
The detector preserves detections from the deliberately low minimum confidence
(`0.001`) and marks detections below the configurable review confidence (`0.25`)
for reviewer attention. The latter is an operational flag, not a calibrated or
decision threshold.

## Human-in-the-loop boundary

This model supplies visual severity evidence only. It does not predict or decide
claim approval, rejection, coverage, payout amount, liability, fraud, repair
cost, or legal responsibility. A human reviewer always makes the final claim
decision.
