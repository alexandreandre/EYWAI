/**
 * Relire le bulletin à l'écran de correction : la logique, sans React.
 *
 * Deux usages qui ne traitent pas l'échec pareil. Après une correction, un
 * rechargement raté se signale sur place. Après une régénération, il doit
 * remonter : le bouton dit alors « Bulletin régénéré, écran non rechargé » au
 * lieu d'un succès posé sur les anciens chiffres.
 */

import { estBulletinIntrouvable } from './bulletinRemplace';

export interface DependancesRechargement<B> {
  /** Null tant qu'il n'y a pas de bulletin à relire. */
  lire: (() => Promise<B>) | null;
  appliquer: (bulletin: B) => void;
  /** 404 : le bulletin a été supprimé ou généré à nouveau. */
  remplace: () => Promise<void>;
  signalerEchec: (erreur: unknown) => void;
  invaliderListes: () => void;
}

export function rechargementsDuBulletin<B>(d: DependancesRechargement<B>) {
  const rechargerOuLever = async () => {
    if (!d.lire) return;
    try {
      d.appliquer(await d.lire());
    } catch (erreur) {
      if (!estBulletinIntrouvable(erreur)) throw erreur;
      await d.remplace();
    }
  };

  const recharger = async () => {
    try {
      await rechargerOuLever();
    } catch (erreur) {
      d.signalerEchec(erreur);
    }
  };

  return {
    recharger,
    apresChangement: async () => {
      await recharger();
      d.invaliderListes();
    },
    /** Pour `onRegenerated` : le serveur a régénéré, les listes suivent même si l'écran échoue. */
    apresRegeneration: async () => {
      try {
        await rechargerOuLever();
      } finally {
        d.invaliderListes();
      }
    },
  };
}
