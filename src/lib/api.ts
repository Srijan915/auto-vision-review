import { FIXTURE_ASSESSMENTS } from "@/lib/fixtures";
import type {
  Assessment,
  CreateAssessmentInput,
  ReviewSubmission,
  Severity,
} from "@/types/claim";

const API_BASE_URL = (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ?? "";
const FIXTURE_KEY = "claimsense.fixture-mode";

/** Fixture mode keeps the app fully interactive without a live FastAPI backend. */
export function isFixtureMode(): boolean {
  if (typeof window === "undefined") return true;
  const stored = window.localStorage.getItem(FIXTURE_KEY);
  if (stored === null) return true;
  return stored === "true";
}

export function setFixtureMode(enabled: boolean) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(FIXTURE_KEY, String(enabled));
}

export function apiBaseUrl() {
  return API_BASE_URL;
}

/* ------------------------------------------------------------------ */
/* In-memory fixture store                                             */
/* ------------------------------------------------------------------ */

let store: Assessment[] | null = null;

function db(): Assessment[] {
  if (!store) store = FIXTURE_ASSESSMENTS.map((a) => structuredClone(a));
  return store;
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

function nextReference() {
  return `CS-2026-${String(420 + db().length).padStart(4, "0")}`;
}

function severityFromDetections(count: number): Severity {
  if (count >= 4) return "Severe";
  if (count >= 2) return "Moderate";
  return "Minor";
}

async function fixtureCreate(input: CreateAssessmentInput): Promise<Assessment> {
  await delay(1400);
  const id = `asm_${Math.random().toString(16).slice(2, 8)}`;
  const now = new Date().toISOString();
  const images = input.files.map((file, i) => {
    const detections = [
      {
        id: `${id}_d${i}a`,
        damage_class: i % 2 === 0 ? "bumper_dent" : "paint_scratch",
        confidence: 0.86 - i * 0.04,
        bbox: { x: 280, y: 320, width: 620, height: 340 },
      },
      {
        id: `${id}_d${i}b`,
        damage_class: "paint_scratch",
        confidence: 0.69,
        bbox: { x: 180, y: 520, width: 480, height: 150 },
      },
    ];
    return {
      id: `${id}_img${i}`,
      url: URL.createObjectURL(file),
      filename: file.name,
      native_width: 1280,
      native_height: 864,
      captured_at: now,
      detections,
    };
  });
  const detectionCount = images.reduce((n, img) => n + img.detections.length, 0);
  const assessment: Assessment = {
    id,
    reference: nextReference(),
    vehicle: {
      make: input.vehicle.make || "Unspecified",
      model: input.vehicle.model || "Unspecified",
      year: input.vehicle.year || new Date().getFullYear(),
      vin: input.vehicle.vin || "VIN NOT SUPPLIED",
      plate: input.vehicle.plate || "—",
      body_style: input.vehicle.body_style || "Unspecified",
    },
    submitted_at: now,
    status: "pending_review",
    human_review_required: true,
    provisional_severity: severityFromDetections(detectionCount),
    model_version: "gemini-2.5-flash",
    detector_version: "yolov8n-damage / v1.4.2",
    images,
    evidence: [
      {
        id: `${id}_ev1`,
        source: "Damage Taxonomy Standard",
        title: "Provisional banding for multi-region surface damage",
        type: "Standard",
        excerpt:
          "Where detections span more than one body region, provisional banding is raised one band pending physical verification.",
        disclaimer:
          "Guidance document. Provisional banding only; a qualified human reviewer must confirm the outcome.",
        retrieved_at: now,
        relevance: 0.86,
      },
      {
        id: `${id}_ev2`,
        source: "Internal Inspection Protocol",
        title: "Photographic evidence sufficiency checklist",
        type: "Protocol",
        excerpt:
          "A wide contextual frame is required alongside close detail frames before assessment sign-off.",
        disclaimer: "Procedural guidance. Not a legal or contractual determination.",
        retrieved_at: now,
        relevance: 0.72,
      },
    ],
    gemini_explanation: `${detectionCount} detections were returned across ${images.length} supplied frame(s). Detection geometry is consistent with surface-level impact damage. Provisional banding is ${severityFromDetections(detectionCount)} and is a technical reading only — human review is mandatory before any outcome is recorded.`,
    review_history: [],
    audit_events: [
      {
        id: `${id}_a1`,
        timestamp: now,
        actor: "intake-service",
        event_type: "assessment.created",
        detail: `${images.length} image(s) accepted from intake channel WEB.`,
      },
      {
        id: `${id}_a2`,
        timestamp: now,
        actor: "yolov8n-damage/v1.4.2",
        event_type: "detection.completed",
        detail: `${detectionCount} detections above 0.60 confidence threshold.`,
      },
      {
        id: `${id}_a3`,
        timestamp: now,
        actor: "gemini-2.5-flash",
        event_type: "explanation.generated",
        detail: "human_review_required set to true.",
      },
    ],
  };
  db().unshift(assessment);
  return structuredClone(assessment);
}

async function fixtureReview(id: string, body: ReviewSubmission): Promise<Assessment> {
  await delay(700);
  const target = db().find((a) => a.id === id);
  if (!target) throw new ApiError(404, "Assessment not found");
  const now = new Date().toISOString();
  const from = target.provisional_severity;
  const to = body.decision === "adjust_severity" ? body.adjusted_severity : undefined;

  target.review_history = [
    ...target.review_history,
    {
      id: `rev_${Math.random().toString(16).slice(2, 8)}`,
      timestamp: now,
      reviewer: body.reviewer,
      decision: body.decision,
      ...(to ? { severity_from: from, severity_to: to } : {}),
      ...(body.notes ? { notes: body.notes } : {}),
    },
  ];
  target.audit_events = [
    ...target.audit_events,
    {
      id: `aud_${Math.random().toString(16).slice(2, 8)}`,
      timestamp: now,
      actor: body.reviewer,
      event_type:
        body.decision === "adjust_severity"
          ? "review.severity_adjusted"
          : "review.decision_recorded",
      detail:
        body.decision === "adjust_severity"
          ? `Severity adjusted ${from} to ${to}.`
          : `Decision: ${body.decision}.`,
    },
  ];
  if (to) target.provisional_severity = to;
  target.status =
    body.decision === "request_reinspection" || body.decision === "adjust_severity"
      ? "pending_review"
      : "reviewed";
  target.human_review_required = target.status === "pending_review";
  return structuredClone(target);
}

/* ------------------------------------------------------------------ */
/* Live FastAPI client                                                 */
/* ------------------------------------------------------------------ */

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE_URL) {
    throw new ApiError(0, "VITE_API_BASE_URL is not configured. Enable fixture mode to continue.");
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(0, `Could not reach the assessment API at ${API_BASE_URL}.`);
  }
  if (!res.ok) {
  const errorText = await res.text();
  throw new ApiError(
    res.status,
    `Request failed (${res.status} ${res.statusText}): ${errorText}`,
  );
}
  return (await res.json()) as T;
}

/* ------------------------------------------------------------------ */
/* Public API                                                          */
/* ------------------------------------------------------------------ */

export async function listAssessments(): Promise<Assessment[]> {
  if (isFixtureMode()) {
    await delay(350);
    return db().map((a) => structuredClone(a));
  }
  return request<Assessment[]>("/assessments");
}

export async function getAssessment(assessmentId: string): Promise<Assessment> {
  if (isFixtureMode()) {
    await delay(350);
    const found = db().find((a) => a.id === assessmentId);
    if (!found) throw new ApiError(404, "Assessment not found.");
    return structuredClone(found);
  }
  return request<Assessment>(`/assessments/${assessmentId}`);
}

export async function createAssessment(input: CreateAssessmentInput): Promise<Assessment> {
  if (isFixtureMode()) return fixtureCreate(input);
  const form = new FormData();
  const file = input.files[0];
if (!file) throw new ApiError(400, "Please select an image.");
form.append("image", file);
  form.append("vehicle", JSON.stringify(input.vehicle));
  if (input.notes) form.append("notes", input.notes);
  return request<Assessment>("/assessments", { method: "POST", body: form });
}

export async function submitReview(
  assessmentId: string,
  body: ReviewSubmission,
): Promise<Assessment> {
  if (isFixtureMode()) return fixtureReview(assessmentId, body);
  return request<Assessment>(`/assessments/${assessmentId}/review`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
