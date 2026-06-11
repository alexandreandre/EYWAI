import type {
  PreflightAnomaly,
  PreflightAnomalyType,
  PreflightResolutionMotif,
} from '@/api/payrollPreflight';

export const PREFLIGHT_ANOMALY_TYPE_LABELS: Record<PreflightAnomalyType, string> = {
  ecart_heures: 'Écart heures',
  heures_non_saisies: 'Heures non saisies',
  pointage: 'Pointage',
  conflit_absence: 'Conflit absence',
};

export const PREFLIGHT_ANOMALY_TYPE_ORDER: PreflightAnomalyType[] = [
  'ecart_heures',
  'heures_non_saisies',
  'pointage',
  'conflit_absence',
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

export function correctionPathForType(type: PreflightAnomalyType): string {
  if (type === 'pointage') return '/badgeuse';
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
