// Saisie d'un nombre à virgule (retour d'Elsa du 17/11 : « montant avec virgule
// pas possible sur les paniers »). Un <input type="number"> rend une valeur vide
// tant que « 7, » n'est pas un nombre complet : `Number('') || 0` remettait le
// champ à 0 au milieu de la frappe. Le texte tapé est gardé tel quel et lu ici.

/** Texte saisi → nombre. Vide → null ; illisible → NaN. Virgule ou point. */
export function lireDecimal(texte: string): number | null {
  // `\s` couvre aussi les espaces insécables (1 234,50 copié d'un tableau).
  const propre = texte.replace(/[\s€%]/g, '').replace(',', '.');
  if (propre === '') return null;
  if (!/^-?\d*\.?\d*$/.test(propre) || propre === '.' || propre === '-') return Number.NaN;
  return Number(propre);
}

/** Nombre → texte affiché, à la française (7.6 → « 7,6 »). */
export function ecrireDecimal(valeur: number | null | undefined): string {
  if (valeur == null || !Number.isFinite(valeur)) return '';
  return String(valeur).replace('.', ',');
}
