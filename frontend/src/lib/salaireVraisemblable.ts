/**
 * Un navigateur qui n'est pas en français lit « 1990,001 » comme 1990001 dans
 * un champ numérique, sans rien dire (recette du 02/10/2026). Le plus haut
 * salaire mensuel en base est alors de 6 696,67 € : au-delà de 15 000 €
 * l'écran demande de vérifier, au-delà de 100 000 € il refuse.
 */
export const SALAIRE_MENSUEL_INHABITUEL = 15000;
export const SALAIRE_MENSUEL_MAXIMUM = 100000;

export const MESSAGE_SALAIRE_TROP_ELEVE =
  'Montant trop élevé pour un salaire mensuel : vérifiez la virgule (tapez par exemple 1990.50).';

export function alerteSalaireInhabituel(salaire: unknown): string | null {
  const montant = typeof salaire === 'number' ? salaire : Number(salaire);
  if (salaire === '' || salaire == null || !Number.isFinite(montant)) return null;
  if (montant <= SALAIRE_MENSUEL_INHABITUEL) return null;
  const lu = montant.toLocaleString('fr-FR', { maximumFractionDigits: 3 });
  return `Salaire mensuel inhabituel : ${lu} €. Si vous avez tapé une virgule, vérifiez qu’elle a bien été prise.`;
}
