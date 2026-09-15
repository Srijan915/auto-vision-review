import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/app-shell";
import { PageHeader, EmptyState } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { assessmentsQuery } from "@/lib/queries";
import { formatDateTime } from "@/lib/format";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [
      { title: "Audit History — ClaimSense" },
      {
        name: "description",
        content:
          "A chronological log of detection runs, evidence retrieval, explanations and recorded human review decisions.",
      },
      { property: "og:title", content: "Audit History — ClaimSense" },
      {
        property: "og:description",
        content: "Chronological audit log of model activity and human review decisions.",
      },
    ],
  }),
  component: AuditPage,
});

function AuditPage() {
  const { data, isLoading, error } = useQuery(assessmentsQuery());

  const events = (data ?? [])
    .flatMap((a) => a.audit_events.map((e) => ({ ...e, reference: a.reference, assessmentId: a.id })))
    .sort((a, b) => b.timestamp.localeCompare(a.timestamp));

  return (
    <AppShell>
      <PageHeader
        eyebrow="Workspace / Audit History"
        title="System and reviewer activity"
        description="Every detection run, evidence retrieval, explanation and human decision is logged in order, with the actor responsible."
      />

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Could not load the audit log</AlertTitle>
          <AlertDescription>{(error as Error).message}</AlertDescription>
        </Alert>
      )}

      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-md" />
          ))}
        </div>
      )}

      {!isLoading && !error && events.length === 0 && (
        <EmptyState
          title="No audit events"
          description="Audit events appear once an assessment has been processed."
        />
      )}

      {events.length > 0 && (
        <ol className="relative space-y-3 border-l border-border pl-6">
          {events.map((e) => (
            <li key={`${e.assessmentId}-${e.id}`} className="relative">
              <span
                className="absolute -left-[29px] top-3 size-2.5 rounded-full border-2 border-background bg-primary"
                aria-hidden
              />
              <div className="rounded-md border border-border bg-card p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-mono text-xs text-primary">{e.event_type}</p>
                  <Link
                    to="/assessments/$assessmentId"
                    params={{ assessmentId: e.assessmentId }}
                    className="focus-ring tech-label text-muted-foreground hover:text-foreground hover:underline"
                  >
                    {e.reference}
                  </Link>
                </div>
                <p className="mt-1 text-sm">{e.detail}</p>
                <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                  {formatDateTime(e.timestamp)} · {e.actor}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </AppShell>
  );
}
