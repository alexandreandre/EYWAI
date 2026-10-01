/**
 * Régénérer un bulletin depuis son écran, puis recharger l'écran.
 *
 * Deux temps distincts : un rechargement en échec après une génération
 * réussie ne doit pas s'afficher « Régénération impossible ».
 */

import type { MessageEcran } from './bulletinRemplace';

export type IssueRegeneration<R> =
  | { kind: 'regenere'; reponse: R }
  | { kind: 'regenere_non_recharge'; reponse: R; erreur: unknown }
  | { kind: 'echec'; erreur: unknown };

export async function regenererPuisRecharger<R>(
  generer: () => Promise<R>,
  recharger: () => Promise<void> | void
): Promise<IssueRegeneration<R>> {
  let reponse: R;
  try {
    reponse = await generer();
  } catch (erreur) {
    return { kind: 'echec', erreur };
  }
  try {
    await recharger();
  } catch (erreur) {
    return { kind: 'regenere_non_recharge', reponse, erreur };
  }
  return { kind: 'regenere', reponse };
}

export function messageRegenereNonRecharge(): MessageEcran {
  return {
    title: 'Bulletin régénéré, écran non rechargé',
    description: 'Rechargez la page pour voir le bulletin recalculé.',
  };
}
