/**
 * Layout de la revue de remplissage IA.
 *
 * Le Dialog n'a qu'un max-height : sans hauteur définie, le flex-1 de la
 * liste n'est pas borné. Le contenu (31 jours) déborde, overflow-hidden le
 * coupe, et rien ne défile. Même schéma que PointageImportDialog.
 */
export function assistedFillDialogHeightClass(hasProposal: boolean): string {
  return hasProposal ? 'h-[90dvh] max-h-[90dvh]' : 'max-h-[90dvh]';
}

/**
 * Bandeau « Consigne texte / N prêts / Vérifiez les jours… ».
 * Inutile en consigne texte : le titre du modal et la liste suffisent.
 */
export function showReviewSummaryBanner(proposal: { source: string }): boolean {
  return proposal.source !== 'texte';
}

/** Retire une ligne lue de la revue (OCR bruit, mauvais rapprochement). */
export function removeReviewRow<T extends { key: string }>(
  rows: T[],
  key: string,
): T[] {
  return rows.filter((row) => row.key !== key);
}

