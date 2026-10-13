/**
 * L'aide sous les lignes de prévoyance, quand aucune n'est saisie.
 *
 * Non-cadre : le moteur applique le barème national. Cadre : il ne pose que les
 * lignes de la fiche, donc rien sans elles ([B4], 12/10/2026).
 */
export function aideLignesPrevoyance(cadre: boolean, nbLignes: number): string | null {
  if (nbLignes > 0) return null;
  return cadre
    ? 'Saisissez les lignes du contrat de prévoyance : sans ligne, le bulletin d’un cadre ne porte aucune cotisation de prévoyance.'
    : 'Sans ligne saisie, le barème national s’applique au bulletin.';
}

// Les taux de prévoyance se saisissent en % et se stockent en fraction, comme le
// moteur les lit ([D1], 13/10/2026). L'arrondi à 12 chiffres efface le bruit du
// ×100 / ÷100 : retaper le taux affiché rend exactement la valeur stockée, et le
// bulletin ne passe pas « À recalculer » pour rien.
const sansBruit = (x: number): number => Number(x.toPrecision(12));

/** Sous un taux de prévoyance qui n'est pas un nombre. */
export const TAUX_PREVOYANCE_INVALIDE = 'Saisissez un taux en %, par exemple 0,78.';

/** Le taux stocké (fraction) tel que le champ l'affiche, en %, virgule décimale. */
export function texteDuTauxPrevoyance(fraction: unknown): string {
  if (fraction === null || fraction === undefined || fraction === '') return '';
  const valeur = Number(fraction);
  if (!Number.isFinite(valeur)) return String(fraction);
  return String(sansBruit(valeur * 100)).replace('.', ',');
}

/** La saisie en % redevenue fraction ; `null` si ce n'est pas un nombre. Vide vaut 0. */
export function fractionDuTexteTaux(texte: string): number | null {
  const propre = texte.trim().replace(/\s/g, '').replace(',', '.');
  if (propre === '') return 0;
  if (!/^[-+]?(\d+\.?\d*|\.\d+)$/.test(propre)) return null;
  return sansBruit(Number(propre) / 100);
}
