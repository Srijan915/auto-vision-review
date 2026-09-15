import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, ShieldAlert } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/status-badges";
import { submitReview } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  DECISION_LABELS,
  SEVERITIES,
  type Assessment,
  type ReviewDecision,
  type Severity,
} from "@/types/claim";

const DECISION_HINTS: Record<ReviewDecision, string> = {
  accept: "Confirm the provisional reading as technically sound.",
  reject: "Record that the detected damage reading is not supported.",
  request_reinspection: "Send back for additional frames or a physical inspection.",
  adjust_severity: "Replace the provisional band with your own assessment.",
};

export function ReviewPanel({
  assessment,
  open,
  onOpenChange,
}: {
  assessment: Assessment;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState<ReviewDecision>("accept");
  const [severity, setSeverity] = useState<Severity>(assessment.provisional_severity);
  const [reviewer, setReviewer] = useState("");
  const [notes, setNotes] = useState("");

  const notesRequired = decision !== "accept";
  const valid = reviewer.trim().length > 1 && (!notesRequired || notes.trim().length > 4);

  const mutation = useMutation({
    mutationFn: () =>
      submitReview(assessment.id, {
        decision,
        reviewer: reviewer.trim(),
        notes: notes.trim(),
        ...(decision === "adjust_severity" ? { adjusted_severity: severity } : {}),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["assessments"] });
      toast.success("Human decision recorded", {
        description: `${DECISION_LABELS[decision]} · ${assessment.reference}`,
      });
      setNotes("");
      onOpenChange(false);
    },
    onError: (error: Error) => {
      toast.error("Could not record the decision", { description: error.message });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Human review — {assessment.reference}</DialogTitle>
          <DialogDescription>
            Your decision is recorded against the assessment. ClaimSense never decides an outcome on
            its own.
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2 rounded-sm border border-moderate/40 bg-moderate/10 px-3 py-2 text-xs text-foreground">
          <ShieldAlert className="size-4 shrink-0 text-moderate" aria-hidden />
          Provisional model banding is{" "}
          <SeverityBadge severity={assessment.provisional_severity} className="ml-1" />
        </div>

        <fieldset className="space-y-2">
          <legend className="tech-label mb-2 text-muted-foreground">Decision</legend>
          <RadioGroup
            value={decision}
            onValueChange={(v) => setDecision(v as ReviewDecision)}
            className="gap-2"
          >
            {(Object.keys(DECISION_LABELS) as ReviewDecision[]).map((key) => (
              <Label
                key={key}
                htmlFor={`decision-${key}`}
                className={cn(
                  "flex cursor-pointer items-start gap-3 rounded-sm border p-3 transition-colors",
                  decision === key ? "border-primary bg-accent/60" : "border-border hover:bg-muted",
                )}
              >
                <RadioGroupItem value={key} id={`decision-${key}`} className="mt-0.5" />
                <span>
                  <span className="block text-sm font-medium">{DECISION_LABELS[key]}</span>
                  <span className="block text-xs font-normal text-muted-foreground">
                    {DECISION_HINTS[key]}
                  </span>
                </span>
              </Label>
            ))}
          </RadioGroup>
        </fieldset>

        {decision === "adjust_severity" && (
          <fieldset>
            <legend className="tech-label mb-2 text-muted-foreground">Adjusted severity</legend>
            <div className="flex flex-wrap gap-2">
              {SEVERITIES.map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={severity === s}
                  onClick={() => setSeverity(s)}
                  className={cn(
                    "focus-ring rounded-sm border px-3 py-2 text-sm transition-colors",
                    severity === s
                      ? "border-primary bg-accent"
                      : "border-border bg-card hover:bg-muted",
                  )}
                >
                  {s}
                </button>
              ))}
            </div>
          </fieldset>
        )}

        <div className="space-y-2">
          <Label htmlFor="reviewer">Reviewer name and role</Label>
          <Input
            id="reviewer"
            value={reviewer}
            placeholder="e.g. S. Iyer (Senior Assessor)"
            onChange={(e) => setReviewer(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="notes">
            Reviewer notes {notesRequired && <span className="text-severe">*</span>}
          </Label>
          <Textarea
            id="notes"
            rows={4}
            value={notes}
            placeholder="Technical observations supporting this decision."
            onChange={(e) => setNotes(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Notes are appended to the review timeline and the audit log.
          </p>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={!valid || mutation.isPending} onClick={() => mutation.mutate()}>
            {mutation.isPending && <Loader2 className="size-4 animate-spin" aria-hidden />}
            Record decision
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
