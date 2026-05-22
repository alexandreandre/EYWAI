import type { ObligationListItem } from "@/api/medicalFollowUp";

export const VISIT_TYPE_LABELS: Record<string, string> = {
  aptitude_sir_avant_affectation: "Aptitude SIR avant affectation",
  vip_avant_affectation_mineur_nuit: "VIP avant affectation (mineur/nuit)",
  reprise: "Reprise",
  vip: "VIP",
  sir: "SIR",
  mi_carriere_45: "Mi-carrière (45 ans)",
  demande: "À la demande",
};

export const STATUS_LABELS: Record<string, string> = {
  a_faire: "À faire",
  planifiee: "Planifiée",
  realisee: "Réalisée",
  annulee: "Annulée",
};

/** Libellés FR des déclencheurs (valeurs backend obligation_engine). */
export const TRIGGER_TYPE_LABELS: Record<string, string> = {
  poste_sir: "Affectation poste SIR",
  nuit_mineur: "Travail de nuit / mineur",
  arret_long: "Arrêt prolongé",
  age_45: "Âge 45 ans (mi-carrière)",
  periodicite_vip: "Périodicité VIP",
  embauche: "Embauche",
  periodicite_sir: "Périodicité SIR",
  demande: "À la demande",
};

export const PRIORITY_LABELS: Record<number, string> = {
  1: "Haute",
  2: "Moyenne",
  3: "Basse",
};

export function formatTriggerType(trigger: string): string {
  return TRIGGER_TYPE_LABELS[trigger] ?? trigger.replace(/_/g, " ");
}

export function formatPriorityLabel(priority: number): string {
  return PRIORITY_LABELS[priority] ?? `Priorité ${priority}`;
}

/** Échéance dans les N prochains jours (inclus), hors retard si excludeOverdue. */
export function isDueWithinDays(
  dueDate: string,
  days: number,
  excludeOverdue = true
): boolean {
  const today = new Date().toISOString().slice(0, 10);
  if (excludeOverdue && dueDate < today) return false;
  const end = new Date();
  end.setDate(end.getDate() + days);
  const endStr = end.toISOString().slice(0, 10);
  return dueDate >= today && dueDate <= endStr;
}

export function formatMedicalDate(s: string | null | undefined): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return s;
  }
}

export function isObligationOverdue(o: ObligationListItem): boolean {
  if (o.status === "realisee" || o.status === "annulee" || !o.due_date) return false;
  const today = new Date().toISOString().slice(0, 10);
  return o.due_date < today;
}

export function statusBadgeVariant(
  status: string,
  dueDate: string
): "default" | "secondary" | "destructive" | "outline" {
  if (status === "realisee" || status === "annulee") return "secondary";
  const today = new Date().toISOString().slice(0, 10);
  if (dueDate < today) return "destructive";
  const d30 = new Date();
  d30.setDate(d30.getDate() + 30);
  if (dueDate <= d30.toISOString().slice(0, 10)) return "outline";
  return "default";
}

/** Libellé relatif à l'échéance (retard ou délai restant). */
export function getDueDateRelativeLabel(dueDate: string | null | undefined, status: string): string | null {
  if (!dueDate || status === "realisee" || status === "annulee") return null;
  const due = new Date(`${dueDate}T12:00:00`);
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const diffMs = due.getTime() - today.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) {
    const n = Math.abs(diffDays);
    return n === 1 ? "En retard de 1 jour" : `En retard de ${n} jours`;
  }
  if (diffDays === 0) return "Échéance aujourd'hui";
  if (diffDays === 1) return "Échéance demain";
  if (diffDays <= 30) return `Échéance dans ${diffDays} jours`;
  return null;
}

export function getNextObligation(obligations: ObligationListItem[]): ObligationListItem | undefined {
  return obligations.find((o) => o.status !== "realisee" && o.status !== "annulee");
}

export interface MedicalObligationCounts {
  overdue: number;
  active: number;
  completed: number;
}

export function countMedicalObligations(obligations: ObligationListItem[]): MedicalObligationCounts {
  let overdue = 0;
  let active = 0;
  let completed = 0;
  for (const o of obligations) {
    if (o.status === "realisee") {
      completed += 1;
      continue;
    }
    if (o.status === "annulee") continue;
    active += 1;
    if (isObligationOverdue(o)) overdue += 1;
  }
  return { overdue, active, completed };
}

const STATUS_SORT: Record<string, number> = {
  a_faire: 0,
  planifiee: 1,
  realisee: 2,
  annulee: 3,
};

/** Actives d'abord, puis par date limite ; annulées en fin de liste. */
export function sortObligationsForDisplay(obligations: ObligationListItem[]): ObligationListItem[] {
  return [...obligations].sort((a, b) => {
    const aAnn = a.status === "annulee" ? 1 : 0;
    const bAnn = b.status === "annulee" ? 1 : 0;
    if (aAnn !== bAnn) return aAnn - bAnn;
    const aDone = a.status === "realisee" ? 1 : 0;
    const bDone = b.status === "realisee" ? 1 : 0;
    if (aDone !== bDone) return aDone - bDone;
    const sa = STATUS_SORT[a.status] ?? 9;
    const sb = STATUS_SORT[b.status] ?? 9;
    if (sa !== sb) return sa - sb;
    return (a.due_date ?? "").localeCompare(b.due_date ?? "");
  });
}

export function obligationMessage(o: ObligationListItem): string {
  if (o.justification) return o.justification;
  if (o.visit_type === "demande" && o.request_motif) {
    const datePart = o.request_date ? ` (${formatMedicalDate(o.request_date)})` : "";
    return `${o.request_motif}${datePart}`;
  }
  if (o.status === "realisee" && o.completed_date) {
    return `Réalisée le ${formatMedicalDate(o.completed_date)}`;
  }
  return "—";
}

export function hasMedicalOverdue(obligations: ObligationListItem[]): boolean {
  return obligations.some(isObligationOverdue);
}
