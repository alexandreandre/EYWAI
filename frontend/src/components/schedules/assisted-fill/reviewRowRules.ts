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

/**
 * Compteur « hors relevé » à jour : celui de l'analyse, moins les salariés
 * associés à la main depuis (plus ceux dont l'association a été défaite).
 */
export function horsReleveRestant(
  initial: number,
  idsAuDepart: (string | null)[],
  idsMaintenant: (string | null)[],
): number {
  const depart = new Set(idsAuDepart.filter(Boolean));
  const maintenant = new Set(idsMaintenant.filter(Boolean));
  let delta = 0;
  maintenant.forEach((id) => {
    if (!depart.has(id)) delta -= 1;
  });
  depart.forEach((id) => {
    if (!maintenant.has(id)) delta += 1;
  });
  return Math.max(0, initial + delta);
}

/**
 * Après « Associer… », la ligne devient prête : sous un filtre qui ne la montre
 * plus (« À vérifier », « Incomplets », « Vides »), on passe à « Tous ».
 */
export function filtreApresAssociation<T extends string>(filtre: T): T | 'all' {
  return filtre === 'all' || filtre === 'ready' ? filtre : 'all';
}
