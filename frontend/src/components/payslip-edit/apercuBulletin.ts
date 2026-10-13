/**
 * Le cadre de l'aperçu, ou rien tant que l'aperçu n'est pas arrivé.
 *
 * Un cadre déjà chargé dont le contenu change ajoute une page à l'historique
 * du navigateur : le premier « Retour » du bulletin ne faisait que revenir au
 * cadre vide (rejeu C2 du 12/10). Chaque aperçu naît donc dans un cadre neuf,
 * de clé propre : sa première page remplace celle du cadre vide, rien ne
 * s'empile.
 */
export function cadreDApercu(
  html: string,
  version: number
): { cle: string; srcDoc: string } | null {
  if (!html) return null;
  return { cle: `apercu-${version}`, srcDoc: html };
}
