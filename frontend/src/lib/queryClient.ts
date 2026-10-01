import { QueryClient } from '@tanstack/react-query';
import { scheduleInvalidateRhSidebarBadges } from '@/lib/invalidateRhSidebarBadges';

export const QUERY_CACHE_KEY = 'eywai-rq-cache-v2';
/** Caches des versions précédentes : v1 gardait les bulletins et la paie du mois 24 h. */
export const LEGACY_QUERY_CACHE_KEYS = ['eywai-rq-cache-v1'] as const;
export const QUERY_CACHE_BUSTER = import.meta.env.VITE_APP_BUILD_ID ?? '20260616-dsn-actif';

export function createAppQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,
        gcTime: 30 * 60 * 1000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });

  queryClient.getMutationCache().subscribe((event) => {
    if (event.type === 'updated' && event.action.type === 'success') {
      scheduleInvalidateRhSidebarBadges(queryClient);
    }
  });

  return queryClient;
}
