/**
 * Taux de la société (AT/MP, versement mobilité, FNAL), enregistrés en points de
 * pourcentage : 0.70 vaut 0,70 %, comme le bulletin l'applique. L'écran
 * multipliait par 100 tout taux inférieur à 1 (« 70.00 % » chez MAJI).
 */

export function tauxAffiche(valeur: number | null | undefined): string {
  if (valeur === null || valeur === undefined || !Number.isFinite(Number(valeur))) return 'N/A';
  return `${Number(valeur).toFixed(2).replace('.', ',')} %`;
}

/** Le champ de saisie repart du taux enregistré, écrit avec une virgule. */
export function tauxEnSaisie(valeur: number | null | undefined): string {
  return valeur === null || valeur === undefined ? '' : String(valeur).replace('.', ',');
}

/** « 0,70 » → 0,7 ; vide → rien à envoyer ; autre chose → message d'erreur. */
export function lireTauxSaisi(saisie: string): { valeur: number | undefined } | { erreur: string } {
  const normalise = saisie.trim().replace(/\s/g, '').replace(',', '.');
  if (normalise === '') return { valeur: undefined };
  if (!/^\d+(\.\d+)?$/.test(normalise)) return { erreur: 'Indiquez un nombre, par exemple 3,66.' };
  return { valeur: Number(normalise) };
}
