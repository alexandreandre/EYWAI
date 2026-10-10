import type { WeekTemplate } from '@/hooks/useCalendar';

/** Jours du modèle de semaine type. Clés 1 à 7, le dimanche portant la clé 7. */
export const JOURS_MODELE_SEMAINE = [
  { label: 'Lundi', key: 1 },
  { label: 'Mardi', key: 2 },
  { label: 'Mercredi', key: 3 },
  { label: 'Jeudi', key: 4 },
  { label: 'Vendredi', key: 5 },
  { label: 'Samedi', key: 6 },
  { label: 'Dimanche', key: 7 },
] as const;

/** Clé du modèle pour un `Date.getDay()` (0 = dimanche). */
export function cleModeleDuJour(dayOfWeek: number): number {
  return dayOfWeek === 0 ? 7 : dayOfWeek;
}

/**
 * Valeur du modèle à appliquer à un jour, ou `undefined` pour le laisser tel quel.
 * Un jour de semaine est toujours appliqué (vide = jour non travaillé) ; le week-end
 * ne l'est que si le modèle y dit quelque chose, pour ne pas effacer un samedi travaillé.
 */
export function valeurModelePourLeJour(
  template: WeekTemplate,
  dayOfWeek: number,
): string | undefined {
  const cle = cleModeleDuJour(dayOfWeek);
  const valeur = template[cle];
  if (cle <= 5) return valeur ?? '';
  return valeur !== undefined && valeur.trim() !== '' ? valeur : undefined;
}
