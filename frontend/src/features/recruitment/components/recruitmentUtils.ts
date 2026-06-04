import type { Candidate, PipelineStage } from "@/api/recruitment";
import { getUserErrorMessage } from "@/lib/errorMessages";

export function recruitmentAiPalette(score: number) {
  if (score >= 80) {
    return {
      bar: "bg-emerald-600",
      badge: "bg-emerald-600 text-white border-emerald-700 shadow-sm",
    };
  }
  if (score >= 60) {
    return {
      bar: "bg-blue-600",
      badge: "bg-blue-600 text-white border-blue-700 shadow-sm",
    };
  }
  if (score >= 40) {
    return {
      bar: "bg-orange-500",
      badge: "bg-orange-500 text-white border-orange-600 shadow-sm",
    };
  }
  return {
    bar: "bg-red-600",
    badge: "bg-red-600 text-white border-red-700 shadow-sm",
  };
}

export const eurFmt = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

export const SEARCH_DEBOUNCE_MS = 300;

export function recruitmentApiErrorMessage(err: unknown): string {
  return getUserErrorMessage(err, 'L’opération a échoué. Réessayez.');
}

/** Pipeline commun à tous les postes (aligné sur le modèle backend par défaut). */
export const UNIFIED_PIPELINE_TEMPLATE: Array<{
  name: string;
  position: number;
  stage_type: PipelineStage["stage_type"];
  is_final: boolean;
}> = [
  { name: "Premier appel", position: 0, stage_type: "standard", is_final: false },
  { name: "Entretien RH", position: 1, stage_type: "standard", is_final: false },
  { name: "Entretien 1", position: 2, stage_type: "standard", is_final: false },
  { name: "Entretien 2", position: 3, stage_type: "standard", is_final: false },
  { name: "Offre envoyée", position: 4, stage_type: "standard", is_final: false },
  { name: "Refusé", position: 5, stage_type: "rejected", is_final: true },
  { name: "Recruté", position: 6, stage_type: "hired", is_final: true },
];

export function unifiedStageId(name: string, stageType: string): string {
  return `unified:${stageType}:${name.toLowerCase().replace(/\s+/g, "-")}`;
}

export function buildUnifiedPipelineStages(): PipelineStage[] {
  return UNIFIED_PIPELINE_TEMPLATE.map((t) => ({
    id: unifiedStageId(t.name, t.stage_type),
    job_id: "unified",
    name: t.name,
    position: t.position,
    is_final: t.is_final,
    stage_type: t.stage_type,
  }));
}

export function unifiedStageKeyForCandidate(c: Candidate): string {
  const type = (c.current_stage_type || "standard").toLowerCase();
  const name = (c.current_stage_name || "").trim();
  if (type === "hired") return unifiedStageId("Recruté", "hired");
  if (type === "rejected") return unifiedStageId("Refusé", "rejected");
  const match = UNIFIED_PIPELINE_TEMPLATE.find(
    (s) => s.stage_type === "standard" && s.name.toLowerCase() === name.toLowerCase(),
  );
  if (match) return unifiedStageId(match.name, match.stage_type);
  return unifiedStageId(UNIFIED_PIPELINE_TEMPLATE[0].name, "standard");
}

export function resolveStageIdForCandidate(
  candidate: Candidate,
  targetUnifiedStageId: string,
  stagesByJobId: Record<string, PipelineStage[]>,
): string | null {
  const unified = buildUnifiedPipelineStages().find((s) => s.id === targetUnifiedStageId);
  if (!unified) return null;
  const jobStages = stagesByJobId[candidate.job_id] ?? [];
  if (unified.stage_type === "hired") {
    return jobStages.find((s) => s.stage_type === "hired")?.id ?? null;
  }
  if (unified.stage_type === "rejected") {
    return jobStages.find((s) => s.stage_type === "rejected")?.id ?? null;
  }
  return (
    jobStages.find(
      (s) =>
        s.stage_type === "standard" &&
        s.name.toLowerCase().trim() === unified.name.toLowerCase().trim(),
    )?.id ??
    jobStages.find((s) => s.stage_type === "standard")?.id ??
    null
  );
}
