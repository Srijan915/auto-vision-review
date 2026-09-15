import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  BookOpen,
  Bot,
  ClipboardList,
  History,
  ScanSearch,
  ShieldAlert,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeader, EmptyState } from "@/components/page-header";
import { AnnotatedImage } from "@/components/annotated-image";
import { ReviewPanel } from "@/components/review-panel";
import {
  ConfidenceMeter,
  HumanReviewBadge,
  SeverityBadge,
  StatusBadge,
} from "@/components/status-badges";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { assessmentQuery } from "@/lib/queries";
import { formatDateTime, titleCase } from "@/lib/format";
import { DECISION_LABELS } from "@/types/claim";

export const Route = createFileRoute("/assessments/$assessmentId")({
  head: () => ({
    meta: [
      { title: "Assessment Detail — ClaimSense" },
      {
        name: "description",
        content:
          "Inspect YOLO damage detections, provisional severity, retrieved evidence, and the model explanation before recording a human review decision.",
      },
      { property: "og:title", content: "Assessment Detail — ClaimSense" },
      {
        property: "og:description",
        content:
          "Damage detections, provisional severity, retrieved evidence, and mandatory human decision capture.",
      },
    ],
  }),
  component: AssessmentDetail,
});

function SectionHeading({
  icon: Icon,
  title,
  hint,
}: {
  icon: typeof BookOpen;
  title: string;
  hint?: string;
}) {
  return (
    <div className="mb-3">
      <h2 className="flex items-center gap-2 text-sm font-semibold">
        <Icon className="size-4 text-primary" aria-hidden />
        {title}
      </h2>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function AssessmentDetail() {
  const { assessmentId } = Route.useParams();
  const { data, isLoading, error } = useQuery(assessmentQuery(assessmentId));
  const [reviewOpen, setReviewOpen] = useState(false);

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-4">
          <Skeleton className="h-24 rounded-md" />
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
            <Skeleton className="h-96 rounded-md" />
            <Skeleton className="h-96 rounded-md" />
          </div>
        </div>
      </AppShell>
    );
  }

  if (error || !data) {
    return (
      <AppShell>
        <Alert variant="destructive">
          <AlertTitle>Assessment unavailable</AlertTitle>
          <AlertDescription>
            {(error as Error)?.message ?? "This assessment could not be found."}
          </AlertDescription>
        </Alert>
        <Button asChild variant="outline" className="mt-4">
          <Link to="/queue">Back to review queue</Link>
        </Button>
      </AppShell>
    );
  }

  const detections = data.images.flatMap((img) => img.detections);

  return (
    <AppShell>
      <Link
        to="/queue"
        className="focus-ring tech-label mb-4 inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        Review queue
      </Link>

      <PageHeader
        eyebrow={`Assessment / ${data.reference}`}
        title={`${data.vehicle.year} ${data.vehicle.make} ${data.vehicle.model}`}
        description={`VIN ${data.vehicle.vin} · ${data.vehicle.plate} · ${data.vehicle.body_style} · submitted ${formatDateTime(data.submitted_at)}`}
        actions={
          <div className="flex flex-col items-end gap-3">
            <div className="flex flex-wrap justify-end gap-2">
              <SeverityBadge severity={data.provisional_severity} />
              <StatusBadge status={data.status} />
              <HumanReviewBadge required={data.human_review_required} />
            </div>
            <Button onClick={() => setReviewOpen(true)}>
              <ClipboardList className="size-4" aria-hidden />
              Record human decision
            </Button>
          </div>
        }
      />

      <Alert className="mb-6 border-moderate/40 bg-moderate/10">
        <ShieldAlert className="size-4 text-moderate" aria-hidden />
        <AlertTitle>Provisional technical reading</AlertTitle>
        <AlertDescription>
          Severity is limited to Minor, Moderate or Severe and reflects visible damage only.
          ClaimSense does not assess coverage, cost, liability or claim outcome.
        </AlertDescription>
      </Alert>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-6">
          <section aria-labelledby="frames">
            <SectionHeading
              icon={ScanSearch}
              title="Detected damage"
              hint={`${data.detector_version} · boxes scaled from each frame's native resolution`}
            />
            <div className="space-y-5">
              {data.images.map((img) => (
                <AnnotatedImage key={img.id} image={img} />
              ))}
            </div>
          </section>

          <section aria-labelledby="detections">
            <SectionHeading icon={ScanSearch} title="Detection table" />
            <div className="overflow-x-auto rounded-md border border-border bg-card">
              <table className="w-full text-sm">
                <caption className="sr-only">Detected damage classes and confidence scores</caption>
                <thead>
                  <tr className="border-b border-border text-left">
                    <th scope="col" className="tech-label px-4 py-2.5 text-muted-foreground">Class</th>
                    <th scope="col" className="tech-label px-4 py-2.5 text-muted-foreground">Confidence</th>
                    <th scope="col" className="tech-label px-4 py-2.5 text-muted-foreground">Box (native px)</th>
                  </tr>
                </thead>
                <tbody>
                  {detections.map((d) => (
                    <tr key={d.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-2.5 font-medium">{titleCase(d.damage_class)}</td>
                      <td className="px-4 py-2.5">
                        <ConfidenceMeter value={d.confidence} />
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                        {d.bbox.x}, {d.bbox.y}, {d.bbox.width}×{d.bbox.height}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section aria-labelledby="evidence">
            <SectionHeading
              icon={BookOpen}
              title="Retrieved evidence"
              hint="Technical sources retrieved to support the provisional reading."
            />
            {data.evidence.length === 0 ? (
              <EmptyState
                title="No evidence retrieved"
                description="No technical documents matched this assessment."
              />
            ) : (
              <ul className="space-y-3">
                {data.evidence.map((e) => (
                  <li key={e.id} className="rounded-md border border-border bg-card p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="tech-label text-primary">
                        {e.source} · {e.type}
                      </p>
                      <span className="font-mono text-xs text-muted-foreground">
                        relevance {(e.relevance * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="mt-1.5 text-sm font-medium">{e.title}</p>
                    <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{e.excerpt}</p>
                    <p className="mt-3 border-l-2 border-moderate/60 pl-3 text-xs italic text-muted-foreground">
                      {e.disclaimer}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <aside className="space-y-6">
          <section aria-labelledby="explanation">
            <SectionHeading
              icon={Bot}
              title="Gemini explanation"
              hint={data.gemini_explanation ? data.model_version : undefined}
            />
            {data.gemini_explanation ? (
              <p className="rounded-md border border-border bg-card p-4 text-sm leading-relaxed">
                {data.gemini_explanation}
              </p>
            ) : (
              <EmptyState
                title="No explanation available"
                description="The explanation model did not return output for this assessment."
              />
            )}
          </section>

          <section aria-labelledby="history">
            <SectionHeading icon={History} title="Review history" />
            {data.review_history.length === 0 ? (
              <EmptyState
                title="No decisions recorded"
                description="This assessment has not been reviewed by a human yet."
              />
            ) : (
              <ol className="relative space-y-4 border-l border-border pl-5">
                {data.review_history.map((r) => (
                  <li key={r.id}>
                    <span
                      className="absolute -left-[5px] mt-1.5 size-2.5 rounded-full bg-primary"
                      aria-hidden
                    />
                    <p className="text-sm font-medium">{DECISION_LABELS[r.decision]}</p>
                    <p className="font-mono text-xs text-muted-foreground">
                      {formatDateTime(r.timestamp)} · {r.reviewer}
                    </p>
                    {r.severity_to && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Severity {r.severity_from} → {r.severity_to}
                      </p>
                    )}
                    {r.notes && <p className="mt-1.5 text-sm text-muted-foreground">{r.notes}</p>}
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section aria-labelledby="audit">
            <SectionHeading icon={ClipboardList} title="Audit events" />
            <ol className="space-y-2">
              {data.audit_events.map((a) => (
                <li
                  key={a.id}
                  className="rounded-sm border border-border bg-card px-3 py-2 text-xs"
                >
                  <p className="font-mono text-[11px] text-primary">{a.event_type}</p>
                  <p className="mt-0.5 text-muted-foreground">{a.detail}</p>
                  <p className="mt-1 font-mono text-[11px] text-muted-foreground/80">
                    {formatDateTime(a.timestamp)} · {a.actor}
                  </p>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>

      <ReviewPanel assessment={data} open={reviewOpen} onOpenChange={setReviewOpen} />
    </AppShell>
  );
}
