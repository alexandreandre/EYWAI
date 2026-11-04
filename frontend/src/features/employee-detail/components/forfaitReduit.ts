/**
 * Forfait jours réduit : nombre de jours par an prévu au contrat du salarié,
 * quand il est inférieur à celui de la société (un jour par semaine : 43 jours).
 * Rangé dans `specificites_paie.forfait_annual_days` ; vide, c'est le forfait
 * de la société. Le moteur en tire le SMIC de la réduction générale (BOSS,
 * allègements généraux, § 860 : SMIC × jours du forfait / 218).
 */
export const JOURS_FORFAIT_LEGAL = 218;

export const MESSAGE_FORFAIT_REDUIT =
  'Un nombre de jours entre 1 et 218 (ex. 43 pour un jour par semaine), ou la case vide pour le forfait de la société.';

/** Jours saisis : un nombre, null pour une case vide, NaN pour une saisie à reprendre. */
export function joursDuForfaitSaisis(texte: string | null | undefined): number | null {
  const brut = (texte ?? '').trim();
  if (!brut) return null;
  const jours = Number(brut.replace(',', '.'));
  return Number.isFinite(jours) && jours > 0 && jours <= JOURS_FORFAIT_LEGAL ? jours : Number.NaN;
}
