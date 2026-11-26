import type {
  PreflightAnomaly,
  PreflightAnomalyType,
  PreflightResolutionMotif,
} from '@/api/payrollPreflight';
import { lienModifierFiche } from '@/features/employee-detail/utils/lienModification';
import { lienCalendrierDuSalarie } from '@/features/payroll/utils/heuresSurArret';

export const PREFLIGHT_ANOMALY_TYPE_LABELS: Record<PreflightAnomalyType, string> = {
  ecart_heures: 'Écart heures',
  heures_non_saisies: 'Heures non saisies',
  pointage: 'Pointage',
  conflit_absence: 'Conflit absence',
  hs_routing_pending: 'HS à arbitrer',
  hs_pointage_a_valider: 'HS pointage à valider',
  fenetre_modifiee: 'Fenêtre modifiée',
  fiche_dsn: 'Fiche à compléter (DSN)',
  absent_a_typer: 'Absent sans type',
  retenue_a_poser: 'Prêt ou saisie à poser',
  prime_a_saisir: 'Prime à saisir',
  minimum_annuel: 'Minimum annuel à vérifier',
  arret_a_confirmer: 'Arrêt à confirmer',
};

export const PREFLIGHT_ANOMALY_TYPE_ORDER: PreflightAnomalyType[] = [
  // Une fiche incomplète refuserait la DSN : à compléter avant le reste.
  'fiche_dsn',
  // Bloque la génération sans forçage : à typer avant le reste.
  'absent_a_typer',
  'hs_routing_pending',
  'hs_pointage_a_valider',
  'ecart_heures',
  'heures_non_saisies',
  'arret_a_confirmer',
  'fenetre_modifiee',
  'pointage',
  'conflit_absence',
  'retenue_a_poser',
  'prime_a_saisir',
  'minimum_annuel',
];

export const PREFLIGHT_RESOLUTION_MOTIF_LABELS: Record<PreflightResolutionMotif, string> = {
  directeur_site: 'Heures confirmées par le directeur de site',
  heures_sup: 'Heures supplémentaires exceptionnelles',
  erreur_pointage_corrigee: 'Erreur de pointage corrigée',
  autre: 'Autre',
};

export const PREFLIGHT_STATUS_LABELS: Record<PreflightAnomaly['status'], string> = {
  a_traiter: 'À traiter',
  justifie: 'Justifié',
  resolu: 'Résolu',
};

export function formatEcartValue(anomaly: PreflightAnomaly): string {
  if (anomaly.ecart == null) return '—';
  const unit = anomaly.is_forfait_jour ? ' j' : ' h';
  const value = anomaly.ecart;
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}${unit}`;
}

/** Types qui se corrigent dans le calendrier du salarié. */
const SE_CORRIGE_AU_CALENDRIER: ReadonlySet<PreflightAnomalyType> = new Set<PreflightAnomalyType>([
  'pointage',
  'absent_a_typer',
  'arret_a_confirmer',
  'ecart_heures',
  'heures_non_saisies',
  'conflit_absence',
]);

/**
 * Le mois où corriger : celui du premier jour en cause (le 24/09 d'une paie
 * d'octobre est dans septembre), sinon le mois de paie contrôlé. Sans mois,
 * le calendrier s'ouvrait sur le mois en cours (Elsa, 26/11 : « les messages
 * restent bloqués sur novembre »).
 */
function moisOuCorriger(
  anomaly: PreflightAnomaly,
  moisDePaie?: { year: number; month: number },
): { year: number; month: number } | undefined {
  const premier = [...(anomaly.jours_manquants ?? [])].sort()[0];
  const m = premier ? /^(\d{4})-(\d{2})-\d{2}$/.exec(premier) : null;
  if (m) return { year: Number(m[1]), month: Number(m[2]) };
  return moisDePaie && moisDePaie.year > 0 ? moisDePaie : undefined;
}

export function verifyPathForAnomaly(
  anomaly: PreflightAnomaly,
  moisDePaie?: { year: number; month: number },
): string {
  if (anomaly.type === 'hs_routing_pending') {
    return '/schedules';
  }
  if (anomaly.type === 'hs_pointage_a_valider') {
    return '/company?tab=paie';
  }
  if (SE_CORRIGE_AU_CALENDRIER.has(anomaly.type) && anomaly.employee_id) {
    // Le calendrier du salarié permet de corriger le pointage et reste dans le
    // périmètre du mode paie (la badgeuse, elle, y est inatteignable).
    return lienCalendrierDuSalarie(anomaly.employee_id, moisOuCorriger(anomaly, moisDePaie));
  }
  if (anomaly.type === 'fiche_dsn') {
    return lienModifierFiche(anomaly.employee_id);
  }
  if (anomaly.type === 'prime_a_saisir') return '/saisies';
  if (anomaly.type === 'retenue_a_poser') {
    return anomaly.sub_type === 'pret' ? '/employee-loans' : '/salary-seizures';
  }
  if (anomaly.type === 'fenetre_modifiee') {
    // Le remède est de régénérer : le lancement de paie.
    return '/payroll';
  }
  return '/schedules';
}

/** @deprecated Utiliser verifyPathForAnomaly */
export function correctionPathForType(type: PreflightAnomalyType): string {
  return '/schedules';
}

export function groupAnomaliesByEmployee(
  anomalies: PreflightAnomaly[],
): Map<string, PreflightAnomaly[]> {
  const map = new Map<string, PreflightAnomaly[]>();
  for (const anomaly of anomalies) {
    const list = map.get(anomaly.employee_id) ?? [];
    list.push(anomaly);
    map.set(anomaly.employee_id, list);
  }
  return map;
}

export function countOpenByType(
  anomalies: PreflightAnomaly[],
  type: PreflightAnomalyType,
): number {
  return anomalies.filter((a) => a.type === type && a.status === 'a_traiter').length;
}

export function countOpenAnomalies(anomalies: PreflightAnomaly[]): number {
  return anomalies.filter((a) => a.status === 'a_traiter').length;
}

export function countOpenBlockingAnomalies(anomalies: PreflightAnomaly[]): number {
  return anomalies.filter((a) => a.status === 'a_traiter' && a.severity === 'bloquant').length;
}
