/**
 * Suppression d'un bulletin : les textes de l'écran, sans React.
 *
 * Le backend répond 204 dès que le bulletin n'est plus là après l'appel ;
 * `dejaSupprime` dit qu'il avait disparu avant (autre écran, autre onglet).
 */

export type MessageDeSuppression = { title: string; description?: string };

export function messageDeSuppression({ dejaSupprime }: { dejaSupprime: boolean }): MessageDeSuppression {
  if (!dejaSupprime) return { title: 'Bulletin supprimé' };
  return {
    title: 'Bulletin déjà supprimé',
    description:
      'Il avait été supprimé depuis un autre écran ou un autre onglet. Rien à refaire : la liste est rechargée.',
  };
}

export interface FenetreDeSuppression {
  titre: string;
  peutSupprimer: boolean;
  explication: string | null;
}

/** Un bulletin validé est refusé par le serveur : la fenêtre le dit d'emblée et donne le bon geste. */
export function fenetreDeSuppression(valide: boolean): FenetreDeSuppression {
  if (!valide) return { titre: 'Supprimer ce bulletin ?', peutSupprimer: true, explication: null };
  return {
    titre: 'Ce bulletin est validé',
    peutSupprimer: false,
    explication:
      'Un bulletin validé ne se supprime pas. Pour le refaire, ouvrez-le et cliquez sur « Régénérer » : l’ancienne version est archivée, la nouvelle est à valider de nouveau.',
  };
}
