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

export const MESSAGE_APERCU_INDISPONIBLE =
  'L’aperçu n’a pas pu être chargé après trois essais. Cliquez sur « Rafraîchir l’aperçu » ; si cela se répète, rechargez la page. Le bulletin enregistré n’est pas touché.';
export const MESSAGE_BULLETIN_DISPARU =
  'Ce bulletin n’existe plus : il a été supprimé ou généré à nouveau. Rouvrez-le depuis la liste des bulletins.';

function statutHttp(error: unknown): number | undefined {
  if (error && typeof error === 'object' && 'response' in error) {
    return (error as { response?: { status?: number } }).response?.status;
  }
  return undefined;
}

const attendreUnPeu = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * Charge l'aperçu, en réessayant seul un échec passager (réseau, serveur
 * occupé) : « Aperçu indisponible pour le moment » apparaissait par
 * intermittence et « Rafraîchir l'aperçu » le faisait revenir (tournage
 * B.1-B.4, 19/10). Un bulletin disparu (404) ne se réessaie pas. Après le
 * dernier essai, un message dit quoi faire.
 */
export async function chargerApercu(
  lire: () => Promise<string>,
  { essais = 3, attendre = attendreUnPeu }: { essais?: number; attendre?: (ms: number) => Promise<void> } = {}
): Promise<{ html: string } | { erreur: string }> {
  for (let essai = 1; essai <= essais; essai += 1) {
    try {
      return { html: await lire() };
    } catch (error) {
      if (statutHttp(error) === 404) return { erreur: MESSAGE_BULLETIN_DISPARU };
      if (essai < essais) await attendre(800 * essai);
    }
  }
  return { erreur: MESSAGE_APERCU_INDISPONIBLE };
}
