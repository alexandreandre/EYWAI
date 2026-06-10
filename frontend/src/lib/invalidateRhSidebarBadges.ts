import type { QueryClient } from '@tanstack/react-query';

/** Préfixe partagé des requêtes de pastilles sidebar RH (voir useRhSidebarTaskBadges). */
export const RH_SIDEBAR_BADGES_QUERY_KEY = ['sidebar-badges'] as const;

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

/** Invalide toutes les requêtes de compteurs sidebar RH pour forcer un rafraîchissement. */
export function invalidateRhSidebarBadges(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: RH_SIDEBAR_BADGES_QUERY_KEY });
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
