import frontLeft from "@/assets/damage-front-left.jpg";
import rearQuarter from "@/assets/damage-rear-quarter.jpg";
import sideDoors from "@/assets/damage-side-doors.jpg";
import type { Assessment } from "@/types/claim";

const W = 1280;
const H = 864;

export const FIXTURE_ASSESSMENTS: Assessment[] = [
  {
    id: "asm_8f31c2",
    reference: "CS-2026-0418",
    vehicle: {
      make: "Nissan",
      model: "Sentra",
      year: 2016,
      vin: "3N1AB7AP4GY230118",
      plate: "KA-05-MJ-7741",
      body_style: "Sedan",
    },
    submitted_at: "2026-09-14T09:12:00Z",
    status: "pending_review",
    human_review_required: true,
    provisional_severity: "Moderate",
    model_version: "gemini-2.5-flash",
    detector_version: "yolov8n-damage / v1.4.2",
    images: [
      {
        id: "img_01",
        url: frontLeft,
        filename: "front_left_corner.jpg",
        native_width: W,
        native_height: H,
        captured_at: "2026-09-14T08:58:00Z",
        detections: [
          {
            id: "det_01",
            damage_class: "broken_headlight",
            confidence: 0.94,
            bbox: { x: 430, y: 214, width: 430, height: 208 },
          },
          {
            id: "det_02",
            damage_class: "bumper_dent",
            confidence: 0.88,
            bbox: { x: 300, y: 402, width: 620, height: 340 },
          },
          {
            id: "det_03",
            damage_class: "paint_scratch",
            confidence: 0.71,
            bbox: { x: 380, y: 560, width: 560, height: 200 },
          },
        ],
      },
      {
        id: "img_02",
        url: sideDoors,
        filename: "driver_side_doors.jpg",
        native_width: W,
        native_height: H,
        captured_at: "2026-09-14T08:59:00Z",
        detections: [
          {
            id: "det_04",
            damage_class: "paint_scratch",
            confidence: 0.9,
            bbox: { x: 150, y: 470, width: 1000, height: 120 },
          },
          {
            id: "det_05",
            damage_class: "shattered_glass",
            confidence: 0.79,
            bbox: { x: 240, y: 200, width: 130, height: 110 },
          },
        ],
      },
    ],
    evidence: [
      {
        id: "ev_01",
        source: "OEM Body Repair Manual",
        title: "Sentra B17 — Front bumper fascia inspection procedure",
        type: "Technical manual",
        excerpt:
          "Inspect fascia for substrate deformation before assessing finish damage. Deformation extending past the reinforcement bar indicates structural involvement requiring workshop inspection.",
        disclaimer:
          "Technical reference only. Not a repair authorisation and not a determination of policy coverage.",
        retrieved_at: "2026-09-14T09:12:41Z",
        relevance: 0.93,
      },
      {
        id: "ev_02",
        source: "Damage Taxonomy Standard",
        title: "Severity banding for lighting assembly damage",
        type: "Standard",
        excerpt:
          "A lighting assembly with lens fracture and compromised housing seal is banded no lower than Moderate pending physical verification.",
        disclaimer:
          "Guidance document. Severity banding is provisional and must be confirmed by a qualified human reviewer.",
        retrieved_at: "2026-09-14T09:12:41Z",
        relevance: 0.87,
      },
      {
        id: "ev_03",
        source: "Internal Inspection Protocol",
        title: "Photographic evidence sufficiency checklist",
        type: "Protocol",
        excerpt:
          "Where damage extends beyond a single panel, a minimum of three angles including a wide contextual frame is required before assessment sign-off.",
        disclaimer:
          "Procedural guidance. Does not constitute a legal or contractual assessment of the claim.",
        retrieved_at: "2026-09-14T09:12:42Z",
        relevance: 0.74,
      },
    ],
    gemini_explanation:
      "Three detections across two frames are consistent with a single low-speed front-left impact. The headlight assembly shows lens fracture with housing intrusion (0.94), and the bumper fascia shows deformation with transfer marking (0.88). The long lateral scratch on the driver side (0.90) sits at a different height and may be unrelated pre-existing damage. Provisional banding is Moderate because the lighting assembly is compromised while panel geometry appears largely intact. Frames do not resolve whether the bumper reinforcement is affected, so physical inspection is required. This is a provisional technical reading only — a human reviewer must confirm it.",
    review_history: [],
    audit_events: [
      {
        id: "aud_01",
        timestamp: "2026-09-14T09:12:00Z",
        actor: "intake-service",
        event_type: "assessment.created",
        detail: "2 images accepted from intake channel WEB.",
      },
      {
        id: "aud_02",
        timestamp: "2026-09-14T09:12:18Z",
        actor: "yolov8n-damage/v1.4.2",
        event_type: "detection.completed",
        detail: "5 detections above 0.60 confidence threshold.",
      },
      {
        id: "aud_03",
        timestamp: "2026-09-14T09:12:42Z",
        actor: "evidence-retriever",
        event_type: "evidence.retrieved",
        detail: "3 documents retrieved from technical corpus.",
      },
      {
        id: "aud_04",
        timestamp: "2026-09-14T09:12:55Z",
        actor: "gemini-2.5-flash",
        event_type: "explanation.generated",
        detail: "Provisional severity Moderate. human_review_required set to true.",
      },
    ],
  },
  {
    id: "asm_2b7d90",
    reference: "CS-2026-0419",
    vehicle: {
      make: "Subaru",
      model: "Impreza",
      year: 2019,
      vin: "JF1GUABC7K8302214",
      plate: "MH-12-QR-3082",
      body_style: "Hatchback",
    },
    submitted_at: "2026-09-14T11:40:00Z",
    status: "pending_review",
    human_review_required: true,
    provisional_severity: "Severe",
    model_version: "gemini-2.5-flash",
    detector_version: "yolov8n-damage / v1.4.2",
    images: [
      {
        id: "img_03",
        url: rearQuarter,
        filename: "rear_left_quarter.jpg",
        native_width: W,
        native_height: H,
        captured_at: "2026-09-14T11:31:00Z",
        detections: [
          {
            id: "det_06",
            damage_class: "panel_dent",
            confidence: 0.91,
            bbox: { x: 340, y: 120, width: 560, height: 380 },
          },
          {
            id: "det_07",
            damage_class: "paint_scratch",
            confidence: 0.83,
            bbox: { x: 650, y: 480, width: 420, height: 230 },
          },
        ],
      },
    ],
    evidence: [
      {
        id: "ev_04",
        source: "Damage Taxonomy Standard",
        title: "Quarter panel deformation banding",
        type: "Standard",
        excerpt:
          "Deformation crossing a body seam or wheel arch boundary is banded Severe pending structural verification.",
        disclaimer:
          "Guidance document. Provisional banding only; final determination requires human reviewer sign-off.",
        retrieved_at: "2026-09-14T11:40:22Z",
        relevance: 0.95,
      },
      {
        id: "ev_05",
        source: "OEM Body Repair Manual",
        title: "Impreza GK/GT — rear quarter structural inspection points",
        type: "Technical manual",
        excerpt:
          "Measure the wheel arch opening at three reference points where visible deformation extends to the arch flange.",
        disclaimer: "Technical reference only. Not a repair authorisation.",
        retrieved_at: "2026-09-14T11:40:23Z",
        relevance: 0.81,
      },
    ],
    gemini_explanation:
      "The quarter panel shows a large-area deformation (0.91) that crosses the body seam toward the rear bumper interface, with associated surface scraping (0.83). The deformation direction suggests a glancing rear-quarter impact. Because deformation crosses a structural seam, provisional banding is Severe. Only one frame was supplied, which is insufficient to confirm the extent — additional angles are recommended. Human review is mandatory.",
    review_history: [],
    audit_events: [
      {
        id: "aud_05",
        timestamp: "2026-09-14T11:40:00Z",
        actor: "intake-service",
        event_type: "assessment.created",
        detail: "1 image accepted from intake channel MOBILE.",
      },
      {
        id: "aud_06",
        timestamp: "2026-09-14T11:40:14Z",
        actor: "yolov8n-damage/v1.4.2",
        event_type: "detection.completed",
        detail: "2 detections above 0.60 confidence threshold.",
      },
      {
        id: "aud_07",
        timestamp: "2026-09-14T11:40:31Z",
        actor: "gemini-2.5-flash",
        event_type: "explanation.generated",
        detail: "Provisional severity Severe. human_review_required set to true.",
      },
    ],
  },
  {
    id: "asm_51aa04",
    reference: "CS-2026-0412",
    vehicle: {
      make: "Volvo",
      model: "XC60",
      year: 2021,
      vin: "YV4A22PK7M1704411",
      plate: "DL-08-CF-9120",
      body_style: "SUV",
    },
    submitted_at: "2026-09-12T15:02:00Z",
    status: "reviewed",
    human_review_required: true,
    provisional_severity: "Minor",
    model_version: "gemini-2.5-flash",
    detector_version: "yolov8n-damage / v1.4.2",
    images: [
      {
        id: "img_04",
        url: sideDoors,
        filename: "driver_side_full.jpg",
        native_width: W,
        native_height: H,
        captured_at: "2026-09-12T14:50:00Z",
        detections: [
          {
            id: "det_08",
            damage_class: "paint_scratch",
            confidence: 0.9,
            bbox: { x: 150, y: 470, width: 1000, height: 120 },
          },
          {
            id: "det_09",
            damage_class: "door_dent",
            confidence: 0.64,
            bbox: { x: 430, y: 430, width: 420, height: 180 },
          },
        ],
      },
    ],
    evidence: [
      {
        id: "ev_06",
        source: "Damage Taxonomy Standard",
        title: "Surface finish damage without substrate deformation",
        type: "Standard",
        excerpt:
          "Linear finish damage with no measurable substrate deformation is banded Minor.",
        disclaimer:
          "Guidance document only. Banding does not determine any contractual outcome.",
        retrieved_at: "2026-09-12T15:02:19Z",
        relevance: 0.88,
      },
    ],
    gemini_explanation:
      "A single long lateral scratch spanning both driver-side doors (0.90) with a low-confidence dent hypothesis (0.64) that is likely a reflection artefact rather than deformation. Provisional banding is Minor. Reviewer confirmation is required for the low-confidence detection.",
    review_history: [
      {
        id: "rev_01",
        timestamp: "2026-09-12T16:18:00Z",
        reviewer: "S. Iyer (Senior Assessor)",
        decision: "adjust_severity",
        severity_from: "Minor",
        severity_to: "Moderate",
        notes:
          "Scratch depth reaches primer along the rear door seam on close inspection. Low-confidence dent dismissed as reflection.",
      },
      {
        id: "rev_02",
        timestamp: "2026-09-12T16:25:00Z",
        reviewer: "S. Iyer (Senior Assessor)",
        decision: "accept",
        notes: "Assessment accepted at adjusted severity. Physical inspection notes attached offline.",
      },
    ],
    audit_events: [
      {
        id: "aud_08",
        timestamp: "2026-09-12T15:02:00Z",
        actor: "intake-service",
        event_type: "assessment.created",
        detail: "1 image accepted from intake channel WEB.",
      },
      {
        id: "aud_09",
        timestamp: "2026-09-12T15:02:19Z",
        actor: "evidence-retriever",
        event_type: "evidence.retrieved",
        detail: "1 document retrieved from technical corpus.",
      },
      {
        id: "aud_10",
        timestamp: "2026-09-12T16:18:00Z",
        actor: "S. Iyer (Senior Assessor)",
        event_type: "review.severity_adjusted",
        detail: "Severity adjusted Minor to Moderate with reviewer notes.",
      },
      {
        id: "aud_11",
        timestamp: "2026-09-12T16:25:00Z",
        actor: "S. Iyer (Senior Assessor)",
        event_type: "review.decision_recorded",
        detail: "Decision: accept.",
      },
    ],
  },
];
