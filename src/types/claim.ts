export type Severity = "Minor" | "Moderate" | "Severe";

export const SEVERITIES: Severity[] = ["Minor", "Moderate", "Severe"];

export type AssessmentStatus = "processing" | "pending_review" | "reviewed";

export type ReviewDecision = "accept" | "reject" | "request_reinspection" | "adjust_severity";

export interface BoundingBox {
  /** Pixel coordinates in the image's native resolution. */
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Detection {
  id: string;
  damage_class: string;
  confidence: number;
  bbox: BoundingBox;
}

export interface AssessmentImage {
  id: string;
  url: string;
  filename: string;
  native_width: number;
  native_height: number;
  captured_at: string;
  detections: Detection[];
}

export interface EvidenceItem {
  id: string;
  source: string;
  title: string;
  type: string;
  excerpt: string;
  disclaimer: string;
  retrieved_at: string;
  relevance: number;
}

export interface ReviewEvent {
  id: string;
  timestamp: string;
  reviewer: string;
  decision: ReviewDecision;
  severity_from?: Severity;
  severity_to?: Severity;
  notes?: string;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  actor: string;
  event_type: string;
  detail: string;
}

export interface Vehicle {
  make: string;
  model: string;
  year: number;
  vin: string;
  plate: string;
  body_style: string;
}

export interface Assessment {
  id: string;
  reference: string;
  vehicle: Vehicle;
  submitted_at: string;
  status: AssessmentStatus;
  human_review_required: boolean;
  provisional_severity: Severity;
  model_version: string;
  detector_version: string;
  images: AssessmentImage[];
  evidence: EvidenceItem[];
  gemini_explanation?: string | null;
  review_history: ReviewEvent[];
  audit_events: AuditEvent[];
}

export interface CreateAssessmentInput {
  vehicle: Partial<Vehicle>;
  files: File[];
  notes?: string;
}

export interface ReviewSubmission {
  decision: ReviewDecision;
  reviewer: string;
  notes: string;
  adjusted_severity?: Severity;
}

export const DECISION_LABELS: Record<ReviewDecision, string> = {
  accept: "Accept assessment",
  reject: "Reject assessment",
  request_reinspection: "Request re-inspection",
  adjust_severity: "Adjust severity",
};
