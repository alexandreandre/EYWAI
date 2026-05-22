import type { AnnualReviewStatus } from "@/api/annualReviews";
import { cn } from "@/lib/utils";
import { annualReviewStatusHelpMessage } from "@/lib/annualReviewFormUtils";
import { SignatureStatusBadge } from "@/components/annual-reviews/SignatureStatusBadge";
import { Check } from "lucide-react";

const STEPS: { status: AnnualReviewStatus; label: string }[] = [
  { status: "planifie", label: "Planifié" },
  { status: "en_attente_acceptation", label: "Acceptation" },
  { status: "accepte", label: "Accepté" },
  { status: "realise", label: "Réalisé" },
  { status: "cloture", label: "Clôturé" },
];

const STATUS_ORDER: AnnualReviewStatus[] = [
  "planifie",
  "en_attente_acceptation",
  "accepte",
  "realise",
  "cloture",
];

function stepIndex(status: AnnualReviewStatus): number {
  if (status === "refuse") return 1;
  const idx = STATUS_ORDER.indexOf(status);
  return idx >= 0 ? idx : 0;
}

interface AnnualReviewWorkflowStepperProps {
  status: AnnualReviewStatus;
  signatureStatus?: string | null;
  className?: string;
}

export function AnnualReviewWorkflowStepper({
  status,
  signatureStatus,
  className,
}: AnnualReviewWorkflowStepperProps) {
  const current = stepIndex(status);
  const isRefused = status === "refuse";
  const help = annualReviewStatusHelpMessage(status);

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-center gap-2">
        {STEPS.map((step, index) => {
          const done = !isRefused && index < current;
          const active = !isRefused && index === current;
          const refusedHere = isRefused && index === 1;

          return (
            <div key={step.status} className="flex items-center gap-2">
              {index > 0 && (
                <div
                  className={cn(
                    "hidden sm:block h-px w-6",
                    done ? "bg-primary" : "bg-border"
                  )}
                />
              )}
              <div className="flex items-center gap-1.5">
                <div
                  className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-medium border",
                    done && "bg-primary text-primary-foreground border-primary",
                    active && "bg-primary/10 text-primary border-primary",
                    refusedHere && "bg-destructive/10 text-destructive border-destructive",
                    !done && !active && !refusedHere && "bg-muted text-muted-foreground border-border"
                  )}
                >
                  {done ? <Check className="h-3.5 w-3.5" /> : index + 1}
                </div>
                <span
                  className={cn(
                    "text-xs sm:text-sm whitespace-nowrap",
                    (active || refusedHere) && "font-medium text-foreground",
                    !active && !refusedHere && "text-muted-foreground"
                  )}
                >
                  {refusedHere ? "Refusé" : step.label}
                </span>
              </div>
            </div>
          );
        })}
        {signatureStatus ? (
          <>
            <div className="hidden sm:block h-px w-6 bg-border" />
            <SignatureStatusBadge status={signatureStatus} />
          </>
        ) : null}
      </div>
      {help ? <p className="text-sm text-muted-foreground">{help}</p> : null}
    </div>
  );
}
