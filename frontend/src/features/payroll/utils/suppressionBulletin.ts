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
