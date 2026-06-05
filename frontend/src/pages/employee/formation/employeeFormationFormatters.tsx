import { Check, X } from "lucide-react";

import type { ComputedStatus } from "@/api/certifications";
import type { LegalObligationStatus } from "@/api/legalObligations";
import type { ProfessionalInterviewStatus } from "@/api/legalObligations";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { competencyLevelLabel } from "@/lib/employeeFormationUtils";

export const TRAINING_TYPE_LABELS: Record<string, string> = {
  presentiel: "Présentiel",
  distanciel: "Distanciel",
  elearning: "E-learning",
  blended: "Blended",
  habilitation: "Habilitation",
};

export function fmtDate(s?: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("fr-FR");
}

export function fmtMoney(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(n);
}

export function categoryLabelFr(cat?: string | null) {
  if (!cat) return "—";
  const m: Record<string, string> = {
    technique: "Technique",
    managériale: "Managériale",
    transversale: "Transversale",
    réglementaire: "Réglementaire",
    sécurité: "Sécurité",
  };
  return m[cat] ?? cat;
}

export function objectiveStatusBadge(status: string) {
  const cfg: Record<string, { label: string; className: string }> = {
    draft: { label: "Brouillon", className: "bg-muted text-muted-foreground" },
    active: { label: "Actif", className: "bg-blue-600 text-white hover:bg-blue-600" },
    achieved: { label: "Atteint", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    partially_achieved: {
      label: "Partiellement atteint",
      className: "bg-orange-500 text-white hover:bg-orange-500",
    },
    not_achieved: { label: "Non atteint", className: "bg-red-600 text-white hover:bg-red-600" },
    cancelled: { label: "Annulé", className: "bg-muted text-muted-foreground" },
  };
  const x = cfg[status] ?? { label: status, className: "bg-muted text-muted-foreground" };
  return <Badge className={x.className}>{x.label}</Badge>;
}

export function objectiveTypeBadge(t: string) {
  const qual = t === "qualitative";
  return (
    <Badge variant="outline" className={qual ? "border-violet-500 text-violet-700" : "border-sky-500 text-sky-700"}>
      {qual ? "Qualitatif" : "Quantitatif"}
    </Badge>
  );
}

export function certStatusBadge(status: ComputedStatus) {
  const cfg: Record<ComputedStatus, { label: string; className: string }> = {
    valid: { label: "Valide", className: "border-0 bg-emerald-600 text-white hover:bg-emerald-600" },
    expiring_soon: {
      label: "Expire bientôt",
      className: "border-0 bg-orange-500 text-white hover:bg-orange-500",
    },
    expired: { label: "Expiré", className: "border-0 bg-red-600 text-white hover:bg-red-600" },
    no_expiry: {
      label: "Sans expiration",
      className: "border-0 bg-muted text-muted-foreground hover:bg-muted",
    },
  };
  const x = cfg[status];
  return <Badge className={x.className}>{x.label}</Badge>;
}

export function trainingAllowsFeedback(status: string): boolean {
  const s = status.toLowerCase();
  return s === "realise" || s === "approuve_rh" || s === "completed";
}

export function enrollmentHidesTrainingFromCatalogAvailability(status: string): boolean {
  const s = status.trim().toLowerCase();
  const showAgain = new Set([
    "annule",
    "annulé",
    "annulee",
    "cancelled",
    "rejete_manager",
    "rejete_rh",
  ]);
  if (showAgain.has(s)) return false;
  const hide = new Set([
    "inscrit",
    "en_cours",
    "realise",
    "completed",
    "approuve_rh",
    "approuve_manager",
    "demande_salarie",
    "in_progress",
    "planned",
  ]);
  return hide.has(s);
}

export function enrollmentStatusBadge(status: string) {
  const s = status.toLowerCase();
  const cfg: Record<string, { label: string; className: string }> = {
    planned: { label: "Planifié", className: "bg-blue-600 text-white hover:bg-blue-600" },
    in_progress: { label: "En cours", className: "bg-orange-500 text-white hover:bg-orange-500" },
    en_cours: { label: "En cours", className: "bg-orange-500 text-white hover:bg-orange-500" },
    inscrit: { label: "Inscrit", className: "bg-sky-600 text-white hover:bg-sky-600" },
    completed: { label: "Terminé", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    realise: { label: "Réalisé", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    cancelled: { label: "Annulé", className: "bg-muted text-muted-foreground" },
    annule: { label: "Annulé", className: "bg-muted text-muted-foreground" },
    demande_salarie: {
      label: "En attente RH",
      className: "bg-amber-400 text-amber-950 hover:bg-amber-400",
    },
    approuve_manager: {
      label: "En attente RH",
      className: "bg-amber-400 text-amber-950 hover:bg-amber-400",
    },
    approuve_rh: { label: "Inscrit", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    rejete_manager: {
      label: "Refusé par le manager",
      className: "bg-red-600 text-white hover:bg-red-600",
    },
    rejete_rh: { label: "Refusé par la RH", className: "bg-red-600 text-white hover:bg-red-600" },
  };
  const x = cfg[s] ?? { label: status, className: "bg-muted text-muted-foreground" };
  return <Badge className={x.className}>{x.label}</Badge>;
}

export function profBadge(st: ProfessionalInterviewStatus) {
  const map: Record<ProfessionalInterviewStatus, { label: string; className: string }> = {
    up_to_date: { label: "À jour", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    due_soon: { label: "Échéance proche", className: "bg-amber-600 text-white hover:bg-amber-600" },
    overdue: { label: "En retard", className: "bg-red-600 text-white hover:bg-red-600" },
    unknown: { label: "Non calculable", className: "bg-muted text-muted-foreground" },
  };
  const x = map[st];
  return <Badge className={x.className}>{x.label}</Badge>;
}

export function sixBadge(st: LegalObligationStatus["six_year_review_status"]) {
  const map: Record<
    LegalObligationStatus["six_year_review_status"],
    { label: string; className: string }
  > = {
    validated: { label: "Validé", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    in_progress: { label: "En cours", className: "bg-sky-600 text-white hover:bg-sky-600" },
    not_validated: { label: "Non validé", className: "bg-red-600 text-white hover:bg-red-600" },
    unknown: { label: "Non calculable", className: "bg-muted text-muted-foreground" },
  };
  const x = map[st];
  return <Badge className={x.className}>{x.label}</Badge>;
}

export function CriterionReadOnly({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {ok ? (
        <Check className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
      ) : (
        <X className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
      )}
      <span className={ok ? "" : "text-muted-foreground"}>{label}</span>
    </div>
  );
}

export function competencyScoreBadge(score: number) {
  const label = competencyLevelLabel(score);
  const map: Record<number, string> = {
    0: "bg-neutral-200 text-neutral-700",
    1: "bg-red-600 text-white hover:bg-red-600",
    2: "bg-orange-500 text-white hover:bg-orange-500",
    3: "bg-green-200 text-green-900",
    4: "bg-green-700 text-white hover:bg-green-700",
  };
  const className = map[score] ?? map[0];
  return <Badge className={cn("border-0", className)}>{label}</Badge>;
}
