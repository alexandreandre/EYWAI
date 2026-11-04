import type { QueryClient } from '@tanstack/react-query';

/** Préfixe partagé des requêtes de pastilles sidebar RH (voir useRhSidebarTaskBadges). */
export const RH_SIDEBAR_BADGES_QUERY_KEY = ['sidebar-badges'] as const;

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

/** Invalide toutes les requêtes de compteurs sidebar RH pour forcer un rafraîchissement. */
export function invalidateRhSidebarBadges(queryClient: QueryClient) {
  return queryClient.invalidateQueries({
    predicate: (query) => query.queryKey.includes(RH_SIDEBAR_BADGES_QUERY_KEY[0]),
  });
}

/** Âge au-delà duquel un changement d'écran relit les compteurs. */
export const AGE_MAX_BADGES_MS = 30_000;

/**
 * Au changement d'écran : relit seulement les compteurs lus il y a plus de 30 s,
 * et pas ceux déjà en cours de lecture. Avant, chaque écran relançait tout
 * (environ 4 appels par salarié pour les calendriers, deux fois : la barre et le
 * bouton « Lancer la paie » montent chacun le hook), audit R2 geste 2.
 */
export function rafraichirBadgesAnciens(queryClient: QueryClient, ageMaxMs = AGE_MAX_BADGES_MS) {
  const maintenant = Date.now();
  return queryClient.invalidateQueries({
    predicate: (query) =>
      query.queryKey.includes(RH_SIDEBAR_BADGES_QUERY_KEY[0]) &&
      query.state.fetchStatus !== 'fetching' &&
      maintenant - query.state.dataUpdatedAt > ageMaxMs,
  });
}

/**
 * Variante débouncée pour éviter une rafale de refetch lors de mutations rapprochées.
 * Utilisée par l'écouteur global du cache de mutations.
 */
export function scheduleInvalidateRhSidebarBadges(queryClient: QueryClient, delayMs = 400) {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }
  debounceTimer = setTimeout(() => {
    debounceTimer = null;
    void invalidateRhSidebarBadges(queryClient);
  }, delayMs);
}
