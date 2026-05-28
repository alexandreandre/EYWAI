import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Candidate, PipelineStage } from "@/api/recruitment";

export function PipelineStageSummaryRow({
  stages,
  candidatesByStage,
}: {
  stages: PipelineStage[];
  candidatesByStage: Record<string, Candidate[]>;
}) {
  const [expanded, setExpanded] = useState(false);
  const scrollToStage = (stageId: string) => {
    document.getElementById(`recruitment-pipeline-stage-${stageId}`)?.scrollIntoView({
      behavior: "smooth",
      inline: "center",
      block: "nearest",
    });
  };

  if (stages.length <= 4) return null;

  if (!expanded) {
    return (
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-8 text-xs text-muted-foreground w-fit -ml-1"
        onClick={() => setExpanded(true)}
      >
        <ChevronDown className="h-3.5 w-3.5 mr-1" />
        Afficher le résumé des étapes ({stages.length})
      </Button>
    );
  }

  return (
    <div className="space-y-1.5">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-7 text-xs text-muted-foreground w-fit -ml-1"
        onClick={() => setExpanded(false)}
      >
        Masquer le résumé des étapes
      </Button>
    <div
      className="flex flex-wrap gap-2 pb-1"
      role="navigation"
      aria-label="Résumé des étapes du pipeline"
    >
      {stages.map((stage) => {
        const count = candidatesByStage[stage.id]?.length ?? 0;
        const isRejected = stage.stage_type === "rejected";
        const isHired = stage.stage_type === "hired";
        return (
          <button
            key={stage.id}
            type="button"
            onClick={() => scrollToStage(stage.id)}
            className={cn(
              "inline-flex min-w-0 max-w-[min(100%,14rem)] items-center gap-2 rounded-lg border px-2.5 py-1.5 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              !isRejected && !isHired && "border-border bg-muted/30 hover:bg-muted/50",
              isRejected && "border-red-200 bg-red-50/50 hover:bg-red-50/70",
              isHired && "border-green-200 bg-green-50/50 hover:bg-green-50/70",
            )}
          >
            <span className="truncate font-medium" title={stage.name}>
              {stage.name}
            </span>
            <Badge variant="secondary" className="h-5 shrink-0 px-1.5 text-[10px] tabular-nums">
              {count}
            </Badge>
          </button>
        );
      })}
    </div>
    </div>
  );
}
