import type { AbsenceBalance, AbsenceRequest } from '@/api/absences';
import { accord } from '@/lib/pluriel';

export const ABSENCE_TYPE_LABELS: Record<AbsenceRequest['type'], string> = {
  conge_paye: 'Congé payé',
  rtt: 'RTT',
  jtc: 'JTC',
  sans_solde: 'Congé sans solde',
  repos_compensateur: 'Repos compensateur',
  recuperation_modulation: 'Récupération modulation',
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

/** Types d'absence enregistrés par l'employeur (pas de demande salarié). */
export const RH_ONLY_ABSENCE_TYPES = [
  'arret_maladie',
  'arret_at',
  'arret_paternite',
  'arret_maternite',
  'arret_maladie_pro',
] as const;

export const EMPLOYEE_REQUESTABLE_ABSENCE_TYPES = [
  'conge_paye',
  'rtt',
  'jtc',
  'repos_compensateur',
  'recuperation_modulation',
  'evenement_familial',
] as const;

export type EmployeeRequestableAbsenceType =
  (typeof EMPLOYEE_REQUESTABLE_ABSENCE_TYPES)[number];

/** Message affiché aux salariés : arrêts, maternité/paternité, maladie pro = saisie employeur. */
export const EMPLOYER_REGISTERED_ABSENCE_HINT =
  'Les arrêts maladie, accidents du travail, congés maternité et paternité (délais selon la convention collective) et maladies professionnelles ne se déclarent pas ici. Contactez votre employeur ou remettez vos justificatifs (certificat médical, etc.) : c’est lui qui enregistre l’absence.';

export function requiresSalaryCertificate(type: string): boolean {
  return (RH_ONLY_ABSENCE_TYPES as readonly string[]).includes(type);
}

export const INSUFFICIENT_CP_BALANCE_MESSAGE =
  'Solde de congés payés insuffisant. Rapprochez-vous de votre direction pour toute demande hors droits acquis.';

/** Quotité d'une demande en jours : une demi-journée (demi_journees) pèse 0,5. */
export function quotiteJoursDemande(req: {
  selected_days?: string[] | null;
  demi_journees?: Record<string, string> | null;
}): number {
  const demi = req.demi_journees ?? {};
  return (req.selected_days ?? []).reduce(
    (sum, day) => sum + (demi[day.slice(0, 10)] ? 0.5 : 1),
    0,
  );
}

/** « 2 », « 2,5 » — quotité de jours pour affichage. */
export function formatQuotiteJours(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1).replace('.', ',');
}

export function getAvailableCongePayeDays(
  balances: AbsenceBalance[],
  pendingRequests: AbsenceRequest[] = [],
): number {
  const row = balances.find((b) => b.type === 'Congés Payés');
  const remaining = typeof row?.remaining === 'number' ? row.remaining : 0;
  const pendingDays = pendingRequests
    .filter((r) => r.type === 'conge_paye' && r.status === 'pending')
    .reduce((sum, r) => sum + quotiteJoursDemande(r), 0);
  return Math.max(0, remaining - pendingDays);
}

/** Avertissement montré à la RH qui pose un congé payé au-delà du solde du salarié. */
export function formatCongeSansSoldeRh(
  prenom: string,
  solde: number,
  demande: number,
): string {
  const excedent = Math.max(0, demande - solde);
  const jours = (n: number) => `${formatQuotiteJours(n)} ${accord(n, 'jour')}`;
  return (
    `Le solde de congés payés de ${prenom} est de ${jours(solde)}. ` +
    `${jours(demande)} ${accord(demande, 'demandé')}. ` +
    `${jours(excedent)} ${accord(excedent, 'excédentaire')} ` +
    `${accord(excedent, 'sera', 'seront')} ${accord(excedent, 'considéré')} comme congé sans solde (non rémunéré). ` +
    'Confirmez-vous cette saisie ?'
  );
}

export function formatCongePayeInsufficientMessage(
  available: number,
  requested: number,
): string {
  if (available <= 0) {
    return INSUFFICIENT_CP_BALANCE_MESSAGE;
  }
  const availLabel = Number.isInteger(available)
    ? String(available)
    : available.toFixed(1);
  const requestedLabel = Number.isInteger(requested)
    ? String(requested)
    : requested.toFixed(1);
  return (
    `Solde de congés payés insuffisant : il vous reste ${availLabel} ${accord(available, 'jour')} ` +
    `${accord(available, 'disponible')} pour ${requestedLabel} ${accord(requested, 'jour')} ${accord(requested, 'demandé')}. ` +
    'Rapprochez-vous de votre direction pour une demande hors solde.'
  );
}

/** Taux (0,5 = 50 %) à la française : « 50 % », « 66,66 % », sans décimale inutile. */
export function formatTauxFr(t: number | null | undefined): string {
  const valeur = Number(t ?? 0);
  const pct = Number.isFinite(valeur) ? Math.round(valeur * 10000) / 100 : 0;
  const texte = Number.isInteger(pct)
    ? String(pct)
    : pct.toFixed(2).replace(/0$/, '').replace('.', ',');
  return `${texte} %`;
}

/** Quantité au format du bulletin : « 6,24 j » (deux décimales), « 10 j » si entière. */
export function formatQuantiteFr(n: number, unit: 'j' | 'h' = 'j'): string {
  const arrondi = Math.round(n * 100) / 100;
  const texte = Number.isInteger(arrondi) ? String(arrondi) : arrondi.toFixed(2).replace('.', ',');
  return `${texte} ${unit}`;
}

export function formatBalanceRemaining(
  remaining: number | string,
  unit: 'j' | 'h' = 'j',
): string {
  if (typeof remaining === 'number') {
    return formatQuantiteFr(remaining, unit);
  }
  if (remaining === 'N/A') return 'Non applicable';
  if (remaining === 'selon événement') return 'Selon événement';
  return String(remaining);
}

/** Soldes exprimés en heures (compte modulation, repos compensateur). */
export function balanceUsesHours(balanceType: string): boolean {
  return balanceType === 'Compte modulation' || balanceType === 'Repos compensateur';
}

const RH_LEAVE_BALANCE_SHORT_LABELS: Record<string, string> = {
  'Congés Payés (période précédente)': 'CP N-1',
  'Congés Payés (période en cours)': 'CP N',
  'Congés Payés': 'CP total',
  'Congés Payés (ancienneté)': 'CP ancienneté',
  'Congés Payés (fractionnement)': 'CP fractionnement',
  RTT: 'RTT',
  'Repos compensateur': 'Repos comp.',
  'Compte modulation': 'Modulation',
  'Événement familial': 'Évén. familial',
};

export function getRhLeaveBalanceShortLabel(type: string): string {
  return RH_LEAVE_BALANCE_SHORT_LABELS[type] ?? type;
}

export function isRhLeaveBalanceVisible(balance: AbsenceBalance): boolean {
  return balance.type !== 'Congé sans solde';
}

export function formatRhLeaveBalanceDetail(
  balance: AbsenceBalance,
): string {
  const unit = balanceUsesHours(balance.type) ? 'h' : 'j';
  const acquired =
    typeof balance.acquired === 'number'
      ? formatQuantiteFr(balance.acquired, unit)
      : '—';
  const taken = formatQuantiteFr(balance.taken, unit);
  const remaining = formatBalanceRemaining(balance.remaining, unit);
  return `Acquis : ${acquired} · Pris : ${taken} · Restant : ${remaining}`;
}

/**
 * Avertissement montré à la RH, dans la fenêtre « Nouveau congé », quand les
 * jours choisis dépassent le solde RTT ou repos compensateur. Le serveur
 * enregistre malgré tout (comportement RH) : on le dit avant, pas après.
 */
export function avertissementSoldeInsuffisantRh(args: {
  type: 'rtt' | 'repos_compensateur';
  prenom: string;
  solde: number;
  /** Jours (RTT) ou heures (repos compensateur) demandés. */
  demande: number;
  /** Repos compensateur : journées sélectionnées sans heures saisies (journée entière). */
  joursSansHeures?: number;
}): string | null {
  const { type, prenom, solde, demande } = args;
  const sansHeures = args.joursSansHeures ?? 0;
  if (type === 'rtt') {
    if (demande <= solde) return null;
    return (
      `Le solde de RTT de ${prenom} est de ${formatQuantiteFr(solde, 'j')} ` +
      `pour ${formatQuantiteFr(demande, 'j')} ${accord(demande, 'demandé')} ; ` +
      'le congé sera enregistré malgré tout.'
    );
  }
  if (sansHeures > 0 ? solde > demande : demande <= solde) return null;
  const demandeTexte =
    sansHeures > 0
      ? `${sansHeures} ${accord(sansHeures, 'journée')} ${accord(sansHeures, 'entière')}`
      : `${formatQuantiteFr(demande, 'h')} ${accord(demande, 'demandée')}`;
  return (
    `Le solde de repos compensateur de ${prenom} est de ${formatQuantiteFr(solde, 'h')} ` +
    `pour ${demandeTexte} ; le repos sera enregistré malgré tout et le solde deviendra négatif.`
  );
}

/** Libellés des types d'arrêt, ceux que propose la fenêtre de saisie. */
const LIBELLES_TYPE_ARRET: Record<string, string> = {
  maladie_simple: 'Maladie simple',
  accident_travail: 'Accident du travail',
  maladie_professionnelle: 'Maladie professionnelle',
  accident_trajet: 'Accident de trajet',
  mi_temps_therapeutique: 'Mi-temps thérapeutique',
  ald: 'ALD',
  rechute_at: 'Rechute AT',
  arret_exceptionnel: 'Arrêt exceptionnel',
  maternite: 'Maternité',
  paternite: "Paternité et accueil de l'enfant",
  adoption: 'Adoption',
};

export function libelleTypeArret(code: string): string {
  return LIBELLES_TYPE_ARRET[code] ?? code;
}

const TYPES_ARRET_MALADIE = [
  'maladie_simple',
  'accident_travail',
  'maladie_professionnelle',
  'accident_trajet',
  'mi_temps_therapeutique',
  'ald',
  'rechute_at',
  'arret_exceptionnel',
] as const;

/** Types d'arrêt proposés pour un type d'absence : un congé maternité ou
 * paternité a les siens (sans carence ; maintien selon le réglage de la
 * société), un arrêt les types de la maladie et de l'accident. */
export function typesArretProposes(
  absenceType: string
): { value: string; label: string }[] {
  const codes: readonly string[] =
    absenceType === 'arret_maternite'
      ? ['maternite', 'adoption']
      : absenceType === 'arret_paternite'
        ? ['paternite', 'adoption']
        : TYPES_ARRET_MALADIE;
  return codes.map((value) => ({ value, label: libelleTypeArret(value) }));
}
