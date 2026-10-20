/**
 * La réponse d'une fenêtre de confirmation : la première seulement. Cliquer sur
 * « Annuler » ferme aussi la fenêtre ; la fermeture ne doit pas répondre une
 * seconde fois.
 */
export function reponseUnique(): {
  promesse: Promise<boolean>;
  repondre: (oui: boolean) => void;
} {
  let resoudre: (oui: boolean) => void = () => {};
  let repondu = false;
  const promesse = new Promise<boolean>((resolve) => {
    resoudre = resolve;
  });
  return {
    promesse,
    repondre: (oui) => {
      if (repondu) return;
      repondu = true;
      resoudre(oui);
    },
  };
}
