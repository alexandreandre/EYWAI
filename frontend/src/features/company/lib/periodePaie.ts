/**
 * Régime de période de paie d'une société — lecture humaine du couple
 * (paie_jour_de_fin, paie_occurrence) consommé par le moteur
 * (backend app/modules/payroll/engine/period_forfait.py::definir_periode_de_paie).
 *
 * Deux régimes réels dans le groupe :
 * - mois civil : jour_de_fin hors 0-6 (l'import DSN pose 28/30/31, un jour du
 *   mois de versement) — la période va du 1er au dernier jour du mois ;
 * - arrêté à l'avant-dernier vendredi : (4, -2) — les variables (heures sup,
 *   pointages) sont comptées en semaines complètes, du lundi qui suit
 *   l'arrêté du mois précédent au dimanche de la semaine de l'avant-dernier
 *   vendredi du mois. Exemple : bulletin de juillet 2026 = 22/06 → 26/07,
 *   soit S26 à S30.
 */

export type RegimePeriodePaie =
  | 'mois_civil'
  | 'avant_dernier_vendredi'
  | 'personnalise'
  | 'non_defini';

export const PAIRE_MOIS_CIVIL = {
  paie_jour_de_fin: 31,
  paie_occurrence: -1,
} as const;

export const PAIRE_AVANT_DERNIER_VENDREDI = {
  paie_jour_de_fin: 4,
  paie_occurrence: -2,
} as const;

/**
 * Miroir de `est_mode_mois_calendaire` côté moteur : un jour hors 0-6 (lundi
 * à dimanche) signifie « mois civil ». L'occurrence absente vaut -2 côté
 * moteur, donc (4, null) est bien l'avant-dernier vendredi.
 */
export function regimePeriodePaie(
  jourDeFin: number | null | undefined,
  occurrence: number | null | undefined,
): RegimePeriodePaie {
  if (jourDeFin === null || jourDeFin === undefined) return 'non_defini';
  if (jourDeFin < 0 || jourDeFin > 6) return 'mois_civil';
  if (
    jourDeFin === PAIRE_AVANT_DERNIER_VENDREDI.paie_jour_de_fin &&
    (occurrence === null ||
      occurrence === undefined ||
      occurrence === PAIRE_AVANT_DERNIER_VENDREDI.paie_occurrence)
  ) {
    return 'avant_dernier_vendredi';
  }
  return 'personnalise';
}

export const LIBELLES_REGIME_PERIODE_PAIE: Record<RegimePeriodePaie, string> = {
  mois_civil: 'Mois civil (du 1er au dernier jour)',
  avant_dernier_vendredi: "Arrêté à l'avant-dernier vendredi",
  personnalise: 'Personnalisé',
  non_defini: 'Non défini',
};

export const DESCRIPTIONS_REGIME_PERIODE_PAIE: Record<RegimePeriodePaie, string> = {
  mois_civil: 'Heures sup, pointages et absences comptés du 1er au dernier jour du mois.',
  avant_dernier_vendredi:
    "Variables comptées en semaines complètes, du lundi qui suit l'arrêté du mois " +
    "précédent au dimanche de la semaine de l'avant-dernier vendredi — paies " +
    'bouclées vers le 24. Exemple : bulletin de juillet 2026 = semaines S26 à S30.',
  personnalise: 'Réglage spécifique (jour de la semaine et occurrence saisis à la main).',
  non_defini: 'Aucun réglage : le moteur applique le mois civil.',
};

export const formatJourDeFin = (day: number | null | undefined): string => {
  if (day === null || day === undefined) return 'Non défini';
  const dayMap: Record<number, string> = {
    0: 'Lundi',
    1: 'Mardi',
    2: 'Mercredi',
    3: 'Jeudi',
    4: 'Vendredi',
    5: 'Samedi',
    6: 'Dimanche',
  };
  return dayMap[day] || String(day);
};

export const formatOccurrence = (occ: number | null | undefined): string => {
  if (occ === null || occ === undefined) return 'Non défini';
  const occurrenceMap: Record<number, string> = {
    '-1': 'Dernier du mois',
    '-2': 'Avant-dernier du mois',
    '-3': 'Antepénultième du mois',
    '1': 'Premier du mois',
    '2': 'Deuxième du mois',
    '3': 'Troisième du mois',
    '4': 'Quatrième du mois',
    '5': 'Cinquième du mois',
  };
  return occurrenceMap[occ] || String(occ);
};
