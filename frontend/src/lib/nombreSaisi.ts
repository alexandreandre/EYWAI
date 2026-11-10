/**
 * Lire un nombre tapé à la main, avec un point ou une virgule (retour B12 du 10/11).
 *
 * « 12,5 », « 12.5 », « 1 234,56 », « 1.234,56 », « 1,234.56 », « -3,5 », « 12 € »
 * se lisent tous. Quand le texte porte à la fois un point et une virgule, le
 * dernier des deux est la virgule décimale, l'autre sépare les milliers. Un
 * seul séparateur est toujours décimal : « 1.234 » vaut 1,234, comme « 1,234 ».
 * Rien de lisible : null, jamais un zéro inventé.
 */
export function lireNombre(saisie: string | number | null | undefined): number | null {
  if (typeof saisie === 'number') return Number.isFinite(saisie) ? saisie : null;
  if (saisie == null) return null;
  let texte = String(saisie).replace(/[\s\u00a0\u202f€%]/g, '').replace(/^\+/, '');
  if (texte === '' || texte === '-') return null;
  const point = texte.lastIndexOf('.');
  const virgule = texte.lastIndexOf(',');
  if (point >= 0 && virgule >= 0) {
    const milliers = point > virgule ? ',' : '.';
    texte = texte.split(milliers).join('');
  }
  texte = texte.replace(',', '.');
  if (!/^-?(\d+\.?\d*|\.\d+)$/.test(texte)) return null;
  const valeur = Number(texte);
  return Number.isFinite(valeur) ? valeur : null;
}
