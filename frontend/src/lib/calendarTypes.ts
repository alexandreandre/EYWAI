/** Libellés et couleurs partagés — calendrier paie (RH et employé). */

export const CALENDAR_TYPE_LABELS: Record<string, string> = {
  travail: 'Travail',
  conge: 'Congé',
  ferie: 'Férié',
  arret_maladie: 'Arrêt maladie',
  weekend: 'Week-end',
};

export const CALENDAR_TYPE_BAR_COLORS: Record<string, string> = {
  travail: 'bg-sky-500',
  conge: 'bg-blue-500',
  ferie: 'bg-purple-500',
  arret_maladie: 'bg-amber-500',
  weekend: 'bg-slate-400',
};

export const CALENDAR_LEGEND_ITEMS: {
  key: string;
  label: string;
  colorClass: string;
}[] = [
  { key: 'travail', label: 'Travail', colorClass: 'bg-sky-500' },
  { key: 'conge', label: 'Congé', colorClass: 'bg-blue-500' },
  { key: 'ferie', label: 'Férié', colorClass: 'bg-purple-500' },
  { key: 'arret_maladie', label: 'Arrêt maladie', colorClass: 'bg-amber-500' },
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
