/** Lecture des `warnings` renvoyés par POST /planned-calendar.
 *
 * Depuis le chantier « calendrier → paie », l'enregistrement d'un planning
 * peut créer ou annuler des demandes de congé VALIDÉES (jours CP/RTT saisis
 * par la RH) et signaler les écarts (solde dépassé, jour antérieur à la
 * reprise, jour couvert par une autre demande, échec de synchronisation).
 * Rien de tout cela ne doit rester silencieux. */

export interface PlanningWarning {
  code?: string;
  jour?: number;
  detail?: string;
  type?: string;
}

export interface PlanningWarningSummary {
  requalifiedCount: number;
  createdCount: number;
  cancelledCount: number;
  /** Messages d'écart à afficher tels quels (déjà rédigés côté serveur). */
  notices: string[];
  hasSyncFailure: boolean;
}

export function summarizePlanningWarnings(
  warnings: PlanningWarning[] | undefined | null,
): PlanningWarningSummary {
  const notices: string[] = [];
  let created = 0;
  let cancelled = 0;
  let requalified = 0;
  let syncFailure = false;
  for (const w of warnings ?? []) {
    switch (w.code) {
      case 'absence_validee_requalifiee':
        requalified += 1;
        break;
      case 'demande_creee_depuis_planning':
        created += 1;
        break;
      case 'demande_planning_annulee':
        cancelled += 1;
        break;
      case 'cp_au_dela_du_solde':
      case 'cp_avant_reprise':
      case 'jour_couvert_par_autre_demande':
        if (w.detail) notices.push(w.detail);
        break;
      case 'sync_absences_echouee':
        syncFailure = true;
        if (w.detail) notices.push(w.detail);
        break;
      default:
        break;
    }
  }
  return {
    requalifiedCount: requalified,
    createdCount: created,
    cancelledCount: cancelled,
    notices,
    hasSyncFailure: syncFailure,
  };
}

export function planningWarningsToast(
  summary: PlanningWarningSummary,
): { title: string; description: string; variant?: 'warning' | 'destructive' } | null {
  const parts: string[] = [];
  if (summary.createdCount > 0) {
    parts.push(
      `${summary.createdCount} demande(s) de congé validée(s) créée(s) depuis le calendrier.`,
    );
  }
  if (summary.cancelledCount > 0) {
    parts.push(
      `${summary.cancelledCount} demande(s) issue(s) du calendrier annulée(s).`,
    );
  }
  if (summary.requalifiedCount > 0) {
    parts.push(
      `${summary.requalifiedCount} jour(s) d'absence validée requalifié(s).`,
    );
  }
  parts.push(...summary.notices);
  if (parts.length === 0) return null;

  const needsAttention =
    summary.hasSyncFailure ||
    summary.requalifiedCount > 0 ||
    summary.notices.length > 0;
  return {
    title: summary.hasSyncFailure
      ? 'Enregistré — action requise'
      : needsAttention
        ? 'Enregistré — à vérifier'
        : 'Enregistré — congés synchronisés',
    description: parts.join(' '),
    variant: summary.hasSyncFailure
      ? 'destructive'
      : needsAttention
        ? 'warning'
        : undefined,
  };
}
