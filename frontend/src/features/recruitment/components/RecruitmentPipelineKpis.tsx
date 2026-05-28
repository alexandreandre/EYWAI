import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  countActionableCandidates,
  countRecruitmentPriorityCandidates,
  type Candidate,
} from "@/api/recruitment";

export function RecruitmentPipelineKpis({
  candidates,
}: {
  candidates: Candidate[];
}) {
  const inProgress = countActionableCandidates(candidates);
  const priorityRh = countRecruitmentPriorityCandidates(candidates);
  const hired = candidates.filter((c) => (c.current_stage_type || "").toLowerCase() === "hired").length;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <Card className="shadow-none">
        <CardContent className="p-4">
          <p className="text-xs font-medium text-muted-foreground">Candidats en cours</p>
          <p className="text-2xl font-bold tabular-nums mt-1">{inProgress}</p>
        </CardContent>
      </Card>
      <Card className={cn("shadow-none", priorityRh > 0 && "border-amber-200/80 bg-amber-50/30")}>
        <CardContent className="p-4">
          <p className="text-xs font-medium text-muted-foreground">Entretien RH à traiter</p>
          <p className="text-2xl font-bold tabular-nums mt-1">{priorityRh}</p>
        </CardContent>
      </Card>
      <Card className="shadow-none">
        <CardContent className="p-4">
          <p className="text-xs font-medium text-muted-foreground">Embauchés</p>
          <p className="text-2xl font-bold tabular-nums mt-1">{hired}</p>
        </CardContent>
      </Card>
    </div>
  );
}
