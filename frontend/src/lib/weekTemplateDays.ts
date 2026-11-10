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

/** Heures d'une case du modèle : vide ou illisible = 0 (jamais une valeur par défaut). */
function heuresDeLaCase(valeur: string | undefined): number {
  const n = Number.parseFloat(String(valeur ?? '').trim().replace(',', '.'));
  return Number.isFinite(n) && n > 0 ? n : 0;
}

/**
 * Le jour prévu que pose une case du modèle. Une case vide vaut 0 h, jour non
 * travaillé : elle n'est plus un « vide » à saisir ensuite (retour du 10/11 :
 * il fallait repasser mettre 0). Au forfait jours, un jour coché vaut 1.
 */
export function jourPrevuDuModele(
  valeur: string | undefined,
  forfaitJours: boolean,
): { type: 'travail' | 'weekend'; heures_prevues: number } {
  const heures = heuresDeLaCase(valeur);
  if (heures <= 0) return { type: 'weekend', heures_prevues: 0 };
  return { type: 'travail', heures_prevues: forfaitJours ? 1 : heures };
}

type JourDeSemaine = { type: 'travail' | 'weekend'; hours: number };
export type SemaineDuModele = Record<
  'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday' | 'saturday' | 'sunday',
  JourDeSemaine
>;

const CLES_SEMAINE = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
] as const;

/**
 * La semaine d'un modèle enregistré, jour par jour. Un jour absent du modèle
 * (case laissée vide à la création) vaut 0 h : il valait 8 h, la valeur par
 * défaut de l'écran (retour du 10/11, modèle « femme de ménage » 6 h/semaine).
 */
export function semaineDuModele(template: WeekTemplate): SemaineDuModele {
  const semaine = {} as SemaineDuModele;
  CLES_SEMAINE.forEach((cle, index) => {
    const heures = heuresDeLaCase(template[index + 1]);
    semaine[cle] = heures > 0 ? { type: 'travail', hours: heures } : { type: 'weekend', hours: 0 };
  });
  return semaine;
}
