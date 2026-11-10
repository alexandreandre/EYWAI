import { isValidElement, type ReactNode } from 'react';

const REPLI = 'L’action n’a pas abouti.';

/**
 * Le serveur peut renvoyer son `detail` en liste d'objets (erreur 422). React refuse de l'afficher, et le
 * Toaster est au-dessus de toute limite d'erreur : sans ceci, un simple message d'erreur vide l'écran.
 */
export function descriptionAffichable(description: unknown): ReactNode {
  if (Array.isArray(description) && !description.some((x) => isValidElement(x))) {
    const texte = description
      .map((x) => (x && typeof x === 'object' && 'msg' in x ? String((x as { msg: unknown }).msg) : typeof x === 'object' ? '' : String(x)))
      .filter(Boolean)
      .join(' ');
    return texte || REPLI;
  }
  if (description && typeof description === 'object' && !Array.isArray(description) && !isValidElement(description)) return REPLI;
  return description as ReactNode;
}
