import type { AbsenceRequest } from '@/api/absences';

export const ABSENCE_TYPE_LABELS: Record<AbsenceRequest['type'], string> = {
  conge_paye: 'Congé payé',
  rtt: 'RTT',
  sans_solde: 'Congé sans solde',
  repos_compensateur: 'Repos compensateur',
  evenement_familial: 'Événement familial',
  arret_maladie: 'Arrêt maladie',
  arret_at: 'Accident du travail',
  arret_paternite: 'Congé paternité',
  arret_maternite: 'Congé maternité',
  arret_maladie_pro: 'Maladie professionnelle',
};

export const EVENEMENT_FAMILIAL_LABELS: Record<string, string> = {
  mariage_salarie: 'Mariage du collaborateur',
  pacs_salarie: 'PACS du collaborateur',
  mariage_enfant: "Mariage d'un enfant",
  naissance_adoption: 'Naissance ou adoption',
  deces_conjoint: 'Décès du conjoint',
  deces_enfant: "Décès d'un enfant",
  deces_pere_mere: 'Décès parent',
  deces_frere_soeur: 'Décès frère/sœur',
  deces_beaux_parents: 'Décès beaux-parents',
  deces_grands_parents: 'Décès grands-parents',
  annonce_handicap_enfant: 'Annonce handicap enfant',
  demenagement: 'Déménagement',
};

const WORKFLOW_STEP_LABELS: Record<string, string> = {
  pending_manager: 'En attente de validation manager',
  approved_manager: 'Validée par le manager — en cours RH',
  rejected_manager: 'Refusée par le manager',
  approved_rh: 'Validée',
  rejected_rh: 'Refusée',
};

export type AbsenceStatusFilter =
  | 'all'
  | 'pending'
  | 'validated'
  | 'rejected'
  | 'cancelled';

export const ABSENCE_STATUS_FILTERS: {
  value: AbsenceStatusFilter;
  label: string;
}[] = [
  { value: 'all', label: 'Toutes' },
  { value: 'pending', label: 'En attente' },
  { value: 'validated', label: 'Validées' },
  { value: 'rejected', label: 'Refusées' },
  { value: 'cancelled', label: 'Annulées' },
];

export function getAbsenceTypeLabel(absence: AbsenceRequest): string {
  if (
    absence.type === 'evenement_familial' &&
    absence.event_subtype
  ) {
    const sub =
      EVENEMENT_FAMILIAL_LABELS[absence.event_subtype] ??
      absence.event_subtype;
    return `Événement familial — ${sub}`;
  }
  return ABSENCE_TYPE_LABELS[absence.type] ?? absence.type;
}

export function formatAbsenceDateRange(days: string[]): string {
  if (!days.length) return 'N/A';
  const sorted = [...days]
    .map((d) => new Date(d))
    .sort((a, b) => a.getTime() - b.getTime());
  const fmt = (d: Date) =>
    d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  if (sorted.length === 1) return fmt(sorted[0]);
  return `${fmt(sorted[0])} → ${fmt(sorted[sorted.length - 1])}`;
}

export function formatAbsenceCreatedAt(createdAt: string): string {
  return new Date(createdAt).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function getWorkflowStepLabel(step: string | null | undefined): string | null {
  if (!step) return null;
  return WORKFLOW_STEP_LABELS[step] ?? null;
}

export function filterAbsencesByStatus(
  absences: AbsenceRequest[],
  filter: AbsenceStatusFilter
): AbsenceRequest[] {
  if (filter === 'all') return absences;
  return absences.filter((a) => a.status === filter);
}

export function absencesOnCalendarDay(
  absences: AbsenceRequest[],
  day: Date
): AbsenceRequest[] {
  const y = day.getFullYear();
  const m = String(day.getMonth() + 1).padStart(2, '0');
  const d = String(day.getDate()).padStart(2, '0');
  const iso = `${y}-${m}-${d}`;
  return absences.filter((a) => a.selected_days?.includes(iso));
}

export function requiresSalaryCertificate(type: string): boolean {
  return [
    'arret_maladie',
    'arret_at',
    'arret_paternite',
    'arret_maternite',
    'arret_maladie_pro',
  ].includes(type);
}

export function formatBalanceRemaining(
  remaining: number | string
): string {
  if (typeof remaining === 'number') {
    return `${remaining.toFixed(1)} j`;
  }
  if (remaining === 'N/A') return 'Non applicable';
  if (remaining === 'selon événement') return 'Selon événement';
  return String(remaining);
}
