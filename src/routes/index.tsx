import { useState } from "react";
import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowRight, Loader2, ScanLine } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeader, EmptyState } from "@/components/page-header";
import { UploadDropzone } from "@/components/upload-dropzone";
import { HumanReviewBadge, SeverityBadge, StatusBadge } from "@/components/status-badges";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { assessmentsQuery } from "@/lib/queries";
import { createAssessment } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Severity } from "@/types/claim";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "ClaimSense — AI Vehicle Damage Review Workspace" },
      {
        name: "description",
        content:
          "Submit vehicle assessment images, inspect YOLO damage detections and provisional severity, and record mandatory human review decisions.",
      },
      { property: "og:title", content: "ClaimSense — AI Vehicle Damage Review Workspace" },
      {
        property: "og:description",
        content:
          "Damage detection review with evidence retrieval, audit history, and mandatory human sign-off.",
      },
    ],
  }),
  component: Dashboard,
});

function StatCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-md border border-border bg-card p-4">
      <p className="tech-label text-muted-foreground">{label}</p>
      <p className="mt-2 font-mono text-3xl tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function Dashboard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery(assessmentsQuery());

  const [files, setFiles] = useState<File[]>([]);
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [plate, setPlate] = useState("");
  const [vin, setVin] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createAssessment({ vehicle: { make, model, plate, vin }, files }),
    onSuccess: async (assessment) => {
      await queryClient.invalidateQueries({ queryKey: ["assessments"] });
      toast.success("Assessment created", {
        description: `${assessment.reference} is awaiting human review.`,
      });
      setFiles([]);
      navigate({ to: "/assessments/$assessmentId", params: { assessmentId: assessment.id } });
    },
    onError: (err: Error) => toast.error("Upload failed", { description: err.message }),
  });

  const counts = (severity: Severity) =>
    (data ?? []).filter((a) => a.provisional_severity === severity).length;
  const awaiting = (data ?? []).filter((a) => a.human_review_required).length;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Workspace / Dashboard"
        title="Damage review overview"
        description="ClaimSense detects and describes visible vehicle damage. It reports provisional severity and retrieved technical evidence — it does not decide outcomes."
      />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Queue summary">
        {isLoading
          ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-md" />)
          : (
            <>
              <StatCard
                label="Assessments"
                value={String(data?.length ?? 0)}
                hint="In the current workspace"
              />
              <StatCard label="Awaiting review" value={String(awaiting)} hint="Human sign-off pending" />
              <StatCard
                label="Moderate band"
                value={String(counts("Moderate"))}
                hint="Provisional model banding"
              />
              <StatCard
                label="Severe band"
                value={String(counts("Severe"))}
                hint="Provisional model banding"
              />
            </>
          )}
      </section>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <section aria-labelledby="recent-heading">
          <h2 id="recent-heading" className="tech-label mb-3 text-muted-foreground">
            Recent assessments
          </h2>

          {error && (
            <Alert variant="destructive">
              <AlertTitle>Could not load assessments</AlertTitle>
              <AlertDescription>{(error as Error).message}</AlertDescription>
            </Alert>
          )}

          {isLoading && (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-24 rounded-md" />
              ))}
            </div>
          )}

          {!isLoading && !error && (data?.length ?? 0) === 0 && (
            <EmptyState
              title="No assessments yet"
              description="Upload vehicle images to create the first assessment. Fixture mode gives you a realistic sample set instantly."
            />
          )}

          <ul className="space-y-3">
            {(data ?? []).map((a) => (
              <li key={a.id}>
                <Link
                  to="/assessments/$assessmentId"
                  params={{ assessmentId: a.id }}
                  className="focus-ring group block rounded-md border border-border bg-card p-4 transition-colors hover:border-primary/50 hover:bg-accent/40"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-mono text-sm text-primary">{a.reference}</p>
                      <p className="mt-0.5 text-sm font-medium">
                        {a.vehicle.year} {a.vehicle.make} {a.vehicle.model}
                      </p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        Submitted {formatDateTime(a.submitted_at)} ·{" "}
                        {a.images.reduce((n, img) => n + img.detections.length, 0)} detections
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={a.provisional_severity} />
                      <StatusBadge status={a.status} />
                      <ArrowRight
                        className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                        aria-hidden
                      />
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="upload-heading" className="space-y-4">
          <h2 id="upload-heading" className="tech-label text-muted-foreground">
            New assessment
          </h2>
          <form
            className="space-y-4 rounded-md border border-border bg-card p-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (files.length === 0) {
                toast.error("Add at least one image");
                return;
              }
              mutation.mutate();
            }}
          >
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="make">Make</Label>
                <Input id="make" value={make} onChange={(e) => setMake(e.target.value)} placeholder="Volvo" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="model">Model</Label>
                <Input id="model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="XC60" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="plate">Plate</Label>
                <Input id="plate" value={plate} onChange={(e) => setPlate(e.target.value)} placeholder="DL-08-CF-9120" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="vin">VIN</Label>
                <Input id="vin" value={vin} onChange={(e) => setVin(e.target.value)} placeholder="YV4A22PK7M1704411" />
              </div>
            </div>

            <UploadDropzone files={files} onChange={setFiles} disabled={mutation.isPending} />

            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <ScanLine className="size-4" aria-hidden />
              )}
              {mutation.isPending ? "Running detection…" : "Run damage detection"}
            </Button>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Detection output is provisional and advisory. Every assessment is routed to a human
              reviewer before any outcome is recorded.
            </p>
          </form>
        </section>
      </div>
    </AppShell>
  );
}
