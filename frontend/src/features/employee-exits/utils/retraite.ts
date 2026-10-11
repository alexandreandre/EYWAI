/**
 * Départ à la retraite : qui en prend l'initiative.
 *
 * Code du travail L1237-9 (départ volontaire : indemnité de D1237-1, soumise aux
 * cotisations) et L1237-7 (mise à la retraite : au moins l'indemnité légale de
 * licenciement, contribution patronale de 40 %). La valeur est rangée dans
 * `exit_notes.retirement_initiator`, que lisent le calcul, le reçu et la DSN
 * (motifs 039 et 038).
 */
export type InitiativeRetraite = 'employee' | 'employer';

export const INITIATIVE_RETRAITE_PAR_DEFAUT: InitiativeRetraite = 'employee';

export const OPTIONS_INITIATIVE_RETRAITE: { value: InitiativeRetraite; label: string }[] = [
  { value: 'employee', label: 'Le salarié (départ volontaire à la retraite)' },
  { value: 'employer', label: "L'employeur (mise à la retraite)" },
];
