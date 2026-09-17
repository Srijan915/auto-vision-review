# ClaimSense Gemini explanations

`GroundedExplanationService` accepts a damage-model analysis result and retrieved
policy/process chunks. It calls Gemini only when at least one approved retrieved
source exists and `GEMINI_API_KEY` is configured in `.env`.

Every response keeps `model_evidence`, `retrieved_evidence`, and `citations`
separate. If retrieval is empty, configuration is absent, or Gemini fails, the
service returns a safe reviewer-facing fallback and does not invent policy
information.

Gemini output is informational only and always requires human review. It does
not make claim approval, coverage, payout, liability, fraud, repair-cost, or
legal decisions.
