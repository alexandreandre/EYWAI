/** La phrase de synthèse de l'encart « Pièces de la société ». */
export function resumePieces(manquantes: number): string {
  if (manquantes === 0) return "Toutes les pièces attendues sont déposées.";
  if (manquantes === 1) return "1 pièce attendue n'est pas encore déposée.";
  return `${manquantes} pièces attendues ne sont pas encore déposées.`;
}
