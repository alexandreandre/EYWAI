import { QueryClient } from '@tanstack/react-query';

export const QUERY_CACHE_KEY = 'eywai-rq-cache-v1';
export const QUERY_CACHE_BUSTER = import.meta.env.VITE_APP_BUILD_ID ?? '1';

export function createAppQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,
        gcTime: 30 * 60 * 1000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });
}
