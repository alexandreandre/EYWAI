/**
 * La DSN déclare cadre ou non-cadre d'après le statut conventionnel repris de
 * l'ancienne DSN (classification), avant le statut de la fiche. Même règle que
 * le serveur (`dsn_export/domain/fiche_a_completer.statut_dsn_contredit_la_fiche`,
 * correspondance de `map_statut_categoriel_rc`) : « 04 » cadre, « 05 » cadre
 * seulement si la fiche l'est, tout autre code non-cadre (Lyon, 17/11/2026).
 */
export function statutDsnContreditLaFiche(
  statutFiche: string | null | undefined,
  classification: { code_statut_dsn?: string | null } | null | undefined,
): string | null {
  const code = String(classification?.code_statut_dsn ?? '').trim();
  if (!code) return null;
  const compact = String(statutFiche ?? '').toLowerCase().replace(/[\s-]/g, '');
  const ficheCadre = compact.includes('cadre') && !compact.includes('noncadre');
  const dsnCadre = code === '04' || (code === '05' && ficheCadre);
  if (ficheCadre === dsnCadre) return null;
  return `La DSN déclare ce salarié ${dsnCadre ? 'cadre' : 'non-cadre'} (statut conventionnel ${code} repris de l'ancienne DSN), la fiche dit « ${ficheCadre ? 'Cadre' : 'Non-cadre'} ». Vérifiez le statut.`;
}
