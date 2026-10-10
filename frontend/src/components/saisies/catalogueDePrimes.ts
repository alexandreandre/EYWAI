/** Chargement du catalogue de primes de la fenêtre de saisie : un échec se dit. */

export const MESSAGE_CATALOGUE_INDISPONIBLE =
  "Le catalogue des primes n'a pas pu être chargé : la liste « Primes Standard » est vide. Fermez puis rouvrez la fenêtre pour réessayer, ou saisissez le nom de la prime à la main.";

export async function chargerCatalogueDePrimes<T>(
  charger: () => Promise<{ data?: T[] | null }>,
): Promise<{ primes: T[]; echec: string | null }> {
  try {
    const reponse = await charger();
    return { primes: reponse.data || [], echec: null };
  } catch {
    return { primes: [], echec: MESSAGE_CATALOGUE_INDISPONIBLE };
  }
}
