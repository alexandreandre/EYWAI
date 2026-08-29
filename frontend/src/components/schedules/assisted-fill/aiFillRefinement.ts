/**
 * Sérialisation de l'état courant de la revue pour une correction IA.
 *
 * La liste des jours affichée (éditions manuelles comprises) est la source de
 * vérité : elle part au backend avec la consigne de correction, et le modèle
 * n'a le droit d'y toucher que là où la consigne le demande.
 */

export interface RefinementDayInput {
  jour: number;
  heures: number | null;
  type: string;
  nature: 'prevu' | 'reel';
}

export interface RefinementRowInput {
  rawName: string;
  matchedName: string | null;
  days: RefinementDayInput[];
}

export interface CurrentProposalPayload {
  employees: { name: string; days: RefinementDayInput[] }[];
}

export function serializeRowsForRefinement(
  rows: RefinementRowInput[],
): CurrentProposalPayload {
  return {
    employees: rows.map((row) => ({
      name: row.matchedName ?? row.rawName,
      days: row.days.map(({ jour, heures, type, nature }) => ({
        jour,
        heures,
        type,
        nature,
      })),
    })),
  };
}
