/**
 * Fin de période d'essai : qui rompt, et le délai de prévenance que Martine
 * calcule (Code du travail L1221-25 et L1221-26). Rangé dans
 * `exit_notes.probation_ended_by` ; DSN 034 (employeur) ou 035 (salarié).
 */
export type InitiativeEssai = 'employer' | 'employee';

export const OPTIONS_INITIATIVE_ESSAI: { value: InitiativeEssai; label: string }[] = [
  { value: 'employer', label: "L'employeur" },
  { value: 'employee', label: 'Le salarié' },
];

export const AIDE_DELAI_PREVENANCE =
  "Délai de prévenance légal : si l'employeur rompt, 24 heures sous 8 jours de présence, 48 heures " +
  "jusqu'à un mois, 2 semaines après un mois, 1 mois après 3 mois (L1221-25) ; si le salarié rompt, " +
  '48 heures, 24 heures sous 8 jours de présence (L1221-26). Martine le calcule depuis la date de ' +
  "notification et verse l'indemnité compensatrice quand l'employeur ne le respecte pas.";
