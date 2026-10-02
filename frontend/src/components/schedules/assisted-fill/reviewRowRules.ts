/**
 * Règles d'une ligne de revue d'import de pointages.
 *
 * Une ligne vide (ancienne fiche badge sans badgeage, semaine sans pointage) ne
 * doit jamais empêcher d'associer son salarié à la ligne qui porte ses heures :
 * le 02/10/2026, une fiche vide rapprochée d'une salariée la retirait de la liste
 * « Associer… » de sa vraie fiche. Même règle que le dédoublonnage du serveur.
 */
export interface ReviewRowLike {
  employeeId: string | null;
  days: { heures: number | null; type: string }[];
}

/** Au moins une heure travaillée, ou un jour d'absence (qui porte une information). */
export function rowCarriesHours(row: ReviewRowLike): boolean {
  return row.days.some((d) => (d.heures ?? 0) > 0 || d.type !== 'travail');
}

/** Salariés que la liste « Associer… » ne propose plus : ceux d'une ligne qui porte des heures. */
export function reservedEmployeeIds(rows: ReviewRowLike[]): string[] {
  return rows
    .filter((r) => r.employeeId && rowCarriesHours(r))
    .map((r) => r.employeeId as string);
}

/** Statut d'une ligne dont le salarié vient d'être associé à une autre ligne. */
export function statusAfterLosingEmployee(row: ReviewRowLike): 'error' | 'empty' {
  return rowCarriesHours(row) ? 'error' : 'empty';
}

/**
 * Avertissements affichés sous une ligne à vérifier : tous. Le premier seul
 * cachait souvent l'essentiel (annotations du relevé derrière une remarque de
 * rapprochement).
 */
export function visibleRowWarnings(warnings: string[], status: string): string[] {
  return status === 'ok' ? [] : warnings;
}
