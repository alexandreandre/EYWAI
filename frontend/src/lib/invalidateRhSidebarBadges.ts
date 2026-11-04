import type { Query, QueryClient } from '@tanstack/react-query';

/** Préfixe partagé des requêtes de pastilles sidebar RH (voir useRhSidebarTaskBadges). */
export const RH_SIDEBAR_BADGES_QUERY_KEY = ['sidebar-badges'] as const;

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

/** Invalide toutes les requêtes de compteurs sidebar RH pour forcer un rafraîchissement. */
export function invalidateRhSidebarBadges(queryClient: QueryClient) {
  return queryClient.invalidateQueries({
    predicate: (query) => query.queryKey.includes(RH_SIDEBAR_BADGES_QUERY_KEY[0]),
  });
}

/**
 * Au changement d'écran : relit seulement les compteurs périmés selon leur
 * propre délai (30 s pour la plupart, 5 min pour les calendriers, qui coûtent
 * environ 3 appels par salarié), et pas ceux déjà en cours de lecture. Avant,
 * chaque écran relançait tout, deux fois : la barre et le bouton « Lancer la
 * paie » montent chacun le hook (audit R2 geste 2). Une mutation réussie, et
 * l'écran des calendriers après une écriture, relisent toujours tout.
 */
export function rafraichirBadgesAnciens(queryClient: QueryClient) {
  return queryClient.invalidateQueries({
    predicate: (query) =>
      query.queryKey.includes(RH_SIDEBAR_BADGES_QUERY_KEY[0]) &&
      query.state.fetchStatus !== 'fetching' &&
      query.isStaleByTime(delaiDuCompteur(query)),
  });
}

/** Le délai de fraîcheur d'un compteur : le plus court de ceux qui l'affichent. */
function delaiDuCompteur(query: Query): number {
  const delais = query.observers
    .map((observer) => observer.options.staleTime)
    .filter((delai): delai is number => typeof delai === 'number');
  return delais.length > 0 ? Math.min(...delais) : 0;
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
