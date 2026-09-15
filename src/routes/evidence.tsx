import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeader, EmptyState } from "@/components/page-header";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { assessmentsQuery } from "@/lib/queries";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/evidence")({
  head: () => ({
    meta: [
      { title: "Evidence Center — ClaimSense" },
      {
        name: "description",
        content:
          "Browse technical manuals, standards and protocols retrieved to support vehicle damage assessments, with source disclaimers.",
      },
      { property: "og:title", content: "Evidence Center — ClaimSense" },
      {
        property: "og:description",
        content: "Retrieved technical sources supporting damage assessments, with disclaimers.",
      },
    ],
  }),
  component: EvidencePage,
});

function EvidencePage() {
  const { data, isLoading, error } = useQuery(assessmentsQuery());
  const [query, setQuery] = useState("");
  const [type, setType] = useState("All");

  const items = (data ?? []).flatMap((a) =>
    a.evidence.map((e) => ({ ...e, assessmentId: a.id, reference: a.reference })),
  );
  const types = ["All", ...Array.from(new Set(items.map((i) => i.type)))];

  const rows = items.filter((i) => {
    if (type !== "All" && i.type !== type) return false;
    if (!query) return true;
    return `${i.title} ${i.source} ${i.excerpt}`.toLowerCase().includes(query.toLowerCase());
  });

  return (
    <AppShell>
      <PageHeader
        eyebrow="Workspace / Evidence Center"
        title="Retrieved technical evidence"
        description="Every source retrieved alongside an assessment, with its type and the disclaimer that governs how it may be used."
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
            aria-label="Search evidence"
            placeholder="Search title, source or excerpt"
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by document type">
          {types.map((t) => (
            <button
              key={t}
              type="button"
              aria-pressed={type === t}
              onClick={() => setType(t)}
              className={cn(
                "focus-ring tech-label rounded-sm border px-2.5 py-2 transition-colors",
                type === t
                  ? "border-primary bg-accent text-accent-foreground"
                  : "border-border bg-card text-muted-foreground hover:bg-muted",
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Could not load evidence</AlertTitle>
          <AlertDescription>{(error as Error).message}</AlertDescription>
        </Alert>
      )}

      {isLoading && (
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-44 rounded-md" />
          ))}
        </div>
      )}

      {!isLoading && !error && rows.length === 0 && (
        <EmptyState
          title="No evidence matches"
          description="Adjust the search term or document type filter."
        />
      )}

      <ul className="grid gap-3 md:grid-cols-2">
        {rows.map((e) => (
          <li key={`${e.assessmentId}-${e.id}`} className="rounded-md border border-border bg-card p-4">
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
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
              <span className="font-mono text-[11px] text-muted-foreground">
                Retrieved {formatDateTime(e.retrieved_at)}
              </span>
              <Link
                to="/assessments/$assessmentId"
                params={{ assessmentId: e.assessmentId }}
                className="focus-ring tech-label text-primary hover:underline"
              >
                {e.reference}
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
