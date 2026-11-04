/** Avancement connu d'un chargement : « 12 sur 42 ». */
export type ProgressionConnue = { faits: number; total: number };

/**
 * Le texte d'un chargement : ce qui se passe, et l'avancement quand on le
 * connaît (« Calcul des bulletins : 12 sur 42 »). Les points de suspension
 * tombent devant le compte.
 */
export function texteDuChargement(
  libelle: string,
  progression?: ProgressionConnue | null,
): string {
  const propre = libelle.trim();
  if (!progression || progression.total <= 0) return propre;
  const faits = Math.min(Math.max(0, Math.round(progression.faits)), progression.total);
  const compte = `${faits} sur ${progression.total}`;
  if (!propre) return compte;
  return `${propre.replace(/\s*(…|\.\.\.)$/, '')} : ${compte}`;
}
