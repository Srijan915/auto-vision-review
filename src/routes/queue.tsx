import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeader, EmptyState } from "@/components/page-header";
import { HumanReviewBadge, SeverityBadge, StatusBadge } from "@/components/status-badges";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { assessmentsQuery } from "@/lib/queries";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { SEVERITIES, type Severity } from "@/types/claim";

export const Route = createFileRoute("/queue")({
  head: () => ({
    meta: [
      { title: "Review Queue — ClaimSense" },
      {
        name: "description",
        content:
          "Filter vehicle damage assessments awaiting mandatory human review by provisional severity and reference.",
      },
      { property: "og:title", content: "Review Queue — ClaimSense" },
      {
        property: "og:description",
        content: "Assessments awaiting mandatory human review, filterable by severity and status.",
      },
    ],
  }),
  component: QueuePage,
});

function QueuePage() {
  const { data, isLoading, error } = useQuery(assessmentsQuery());
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState<Severity | "All">("All");
  const [pendingOnly, setPendingOnly] = useState(false);

  const rows = (data ?? []).filter((a) => {
    const haystack = `${a.reference} ${a.vehicle.make} ${a.vehicle.model} ${a.vehicle.plate}`.toLowerCase();
    if (query && !haystack.includes(query.toLowerCase())) return false;
    if (severity !== "All" && a.provisional_severity !== severity) return false;
    if (pendingOnly && !a.human_review_required) return false;
    return true;
  });

  return (
    <AppShell>
      <PageHeader
        eyebrow="Workspace / Review Queue"
        title="Assessments awaiting a reviewer"
        description="Each row shows the detector output and provisional severity band. Open an assessment to inspect the frames before recording a decision."
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-56 flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search reference, vehicle or plate"
            aria-label="Search assessments"
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by severity">
          {(["All", ...SEVERITIES] as const).map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={severity === s}
              onClick={() => setSeverity(s)}
              className={cn(
                "focus-ring tech-label rounded-sm border px-2.5 py-2 transition-colors",
                severity === s
                  ? "border-primary bg-accent text-accent-foreground"
                  : "border-border bg-card text-muted-foreground hover:bg-muted",
              )}
            >
              {s}
            </button>
          ))}
        </div>
        <button
          type="button"
          aria-pressed={pendingOnly}
          onClick={() => setPendingOnly((v) => !v)}
          className={cn(
            "focus-ring tech-label rounded-sm border px-2.5 py-2 transition-colors",
            pendingOnly
              ? "border-moderate/50 bg-moderate/12 text-moderate"
              : "border-border bg-card text-muted-foreground hover:bg-muted",
          )}
        >
          Pending review only
        </button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Could not load the queue</AlertTitle>
          <AlertDescription>{(error as Error).message}</AlertDescription>
        </Alert>
      )}

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-md" />
          ))}
        </div>
      )}

      {!isLoading && !error && rows.length === 0 && (
        <EmptyState
          title="Nothing matches these filters"
          description="Clear the search or severity filter to see the rest of the queue."
        />
      )}

      <ul className="space-y-3">
        {rows.map((a) => (
          <li key={a.id}>
            <Link
              to="/assessments/$assessmentId"
              params={{ assessmentId: a.id }}
              className="focus-ring block rounded-md border border-border bg-card p-4 transition-colors hover:border-primary/50 hover:bg-accent/40"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-mono text-sm text-primary">{a.reference}</p>
                  <p className="mt-0.5 text-sm font-medium">
                    {a.vehicle.year} {a.vehicle.make} {a.vehicle.model} · {a.vehicle.body_style}
                  </p>
                  <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                    VIN {a.vehicle.vin} · {a.vehicle.plate}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {formatDateTime(a.submitted_at)} · {a.images.length} frame(s) ·{" "}
                    {a.images.reduce((n, img) => n + img.detections.length, 0)} detections ·{" "}
                    {a.detector_version}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={a.provisional_severity} />
                  <StatusBadge status={a.status} />
                  <HumanReviewBadge required={a.human_review_required} />
                </div>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
