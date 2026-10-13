type Naissance = { lieu_naissance?: string | null; nationalite?: string | null };

/**
 * Ce que la DSN demandera et que la fiche n'a pas : le lieu de naissance et la
 * nationalité sont facultatifs à l'embauche, jamais bloquants.
 */
export function avertissementNaissanceDsn(valeurs: Naissance): string | null {
  const manque: string[] = [];
  if (!valeurs.lieu_naissance?.trim()) manque.push('le lieu de naissance');
  if (!valeurs.nationalite?.trim()) manque.push('la nationalité');
  if (manque.length === 0) return null;
  return `La DSN demandera ${manque.join(' et ')} : à compléter avant son dépôt.`;
}
