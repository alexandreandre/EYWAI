/** Libellés et couleurs partagés — calendrier paie (RH et employé).
 *
 * SOURCE UNIQUE : toutes les vues (semaine équipe, calendrier complet,
 * popup jour, légendes) doivent consommer ces maps — congé en vert, arrêt
 * en rouge, partout pareil (demande Gaëlle 03/09). `conges_payes` et `rtt`
 * sont les types que la validation d'absence écrit côté backend
 * (ABSENCE_TYPE_TO_CALENDAR_TYPE) ; `work` est l'alias écrit par
 * l'application de modèle de semaine. */

export const CALENDAR_TYPE_LABELS: Record<string, string> = {
  travail: 'Travail',
  work: 'Travail',
  conge: 'Congé',
  conges_payes: 'Congés payés',
  rtt: 'RTT',
  ferie: 'Férié',
  arret_maladie: 'Arrêt maladie',
  weekend: 'Week-end',
  repos: 'Repos',
};

export const CALENDAR_TYPE_BAR_COLORS: Record<string, string> = {
  travail: 'bg-sky-500',
  work: 'bg-sky-500',
  conge: 'bg-green-500',
  conges_payes: 'bg-green-500',
  rtt: 'bg-teal-500',
  ferie: 'bg-purple-500',
  arret_maladie: 'bg-red-500',
  weekend: 'bg-slate-400',
  repos: 'bg-slate-400',
};

/** Fonds de cellule/carte teintés par type (mêmes teintes que la vue semaine). */
export const CALENDAR_TYPE_BG_COLORS: Record<string, string> = {
  travail: 'bg-sky-50 hover:bg-sky-100 border-sky-200/60',
  work: 'bg-sky-50 hover:bg-sky-100 border-sky-200/60',
  conge: 'bg-green-50 hover:bg-green-100 border-green-200/60',
  conges_payes: 'bg-green-50 hover:bg-green-100 border-green-200/60',
  rtt: 'bg-teal-50 hover:bg-teal-100 border-teal-200/60',
  ferie: 'bg-purple-50 hover:bg-purple-100 border-purple-200/60',
  arret_maladie: 'bg-red-50 hover:bg-red-100 border-red-200/60',
  weekend: 'bg-slate-50 hover:bg-slate-100 border-slate-200/60',
  repos: 'bg-slate-50 hover:bg-slate-100 border-slate-200/60',
};

export const CALENDAR_LEGEND_ITEMS: {
  key: string;
  label: string;
  colorClass: string;
}[] = [
  { key: 'travail', label: 'Travail', colorClass: 'bg-sky-500' },
  { key: 'conge', label: 'Congé', colorClass: 'bg-green-500' },
  { key: 'rtt', label: 'RTT', colorClass: 'bg-teal-500' },
  { key: 'ferie', label: 'Férié', colorClass: 'bg-purple-500' },
  { key: 'arret_maladie', label: 'Arrêt maladie', colorClass: 'bg-red-500' },
  { key: 'weekend', label: 'Week-end', colorClass: 'bg-slate-400' },
  { key: 'today', label: "Aujourd'hui", colorClass: 'ring-2 ring-primary' },
];

export function getCalendarTypeLabel(type: string | null | undefined): string {
  if (!type) return 'Week-end';
  return CALENDAR_TYPE_LABELS[type] ?? type;
}

export function formatCalendarValue(
  value: number | null | undefined,
  isForfaitJour: boolean
): string {
  if (value === null || value === undefined) return '–';
  if (isForfaitJour) {
    return value === 1 ? 'Oui (journée)' : 'Non';
  }
  return `${value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} h`;
}
