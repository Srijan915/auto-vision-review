import { AlertTriangle, CircleCheck, UserCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AssessmentStatus, Severity } from "@/types/claim";

const SEVERITY_STYLES: Record<Severity, string> = {
  Minor: "border-minor/40 bg-minor/10 text-minor",
  Moderate: "border-moderate/45 bg-moderate/12 text-moderate",
  Severe: "border-severe/45 bg-severe/12 text-severe",
};

export function SeverityBadge({
  severity,
  className,
}: {
  severity: Severity;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "tech-label inline-flex items-center gap-1.5 rounded-sm border px-2 py-1",
        SEVERITY_STYLES[severity],
        className,
      )}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {severity}
    </span>
  );
}

export function HumanReviewBadge({ required }: { required: boolean }) {
  return (
    <span
      className={cn(
        "tech-label inline-flex items-center gap-1.5 rounded-sm border px-2 py-1",
        required
          ? "border-moderate/45 bg-moderate/12 text-moderate"
          : "border-border bg-muted text-muted-foreground",
      )}
    >
      {required ? (
        <AlertTriangle className="size-3" aria-hidden />
      ) : (
        <CircleCheck className="size-3" aria-hidden />
      )}
      human_review_required: {String(required)}
    </span>
  );
}

const STATUS_LABEL: Record<AssessmentStatus, string> = {
  processing: "Processing",
  pending_review: "Awaiting human review",
  reviewed: "Reviewed",
};

export function StatusBadge({ status }: { status: AssessmentStatus }) {
  return (
    <span
      className={cn(
        "tech-label inline-flex items-center gap-1.5 rounded-sm border px-2 py-1",
        status === "reviewed"
          ? "border-steel/40 bg-steel/10 text-primary"
          : "border-border bg-secondary text-secondary-foreground",
      )}
    >
      <UserCheck className="size-3" aria-hidden />
      {STATUS_LABEL[status]}
    </span>
  );
}

export function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2" title={`Confidence ${pct}%`}>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="font-mono text-xs tabular-nums text-muted-foreground">{pct}%</span>
    </div>
  );
}
