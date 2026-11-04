import { MutationCache, QueryClient } from '@tanstack/react-query';
import axios from 'axios';

import { toast } from '@/hooks/use-toast';
import { getUserErrorMessage } from '@/lib/errorMessages';
import { scheduleInvalidateRhSidebarBadges } from '@/lib/invalidateRhSidebarBadges';

export const QUERY_CACHE_KEY = 'martine-rq-cache-v2';
/** Caches des versions précédentes : v1 gardait les bulletins et la paie du mois 24 h. */
export const LEGACY_QUERY_CACHE_KEYS = ['martine-rq-cache-v1'] as const;
export const QUERY_CACHE_BUSTER = import.meta.env.VITE_APP_BUILD_ID ?? '20260616-dsn-actif';

/** Ce qu'une mutation peut dire au filet global d'erreurs. */
export type MetaDeMutation = {
  /**
   * L'écran affiche déjà l'échec lui-même (message dans la page, ou appelant de
   * `mutateAsync` qui attrape l'erreur et la montre) : le filet se tait.
   */
  erreurAffichee?: boolean;
};

declare module '@tanstack/react-query' {
  interface Register {
    mutationMeta: MetaDeMutation;
  }
}

export const TITRE_ECHEC_MUTATION = 'L’action n’a pas abouti';

/**
 * Filet global : une mutation qui échoue le dit toujours. Un seul message par
 * échec : si l'écran a son propre `onError`, ou s'il affiche l'erreur lui-même
 * (`meta.erreurAffichee`), le filet ne dit rien.
 */
function signalerEchecDeMutation(
  error: unknown,
  mutation: { options: { onError?: unknown }; meta?: MetaDeMutation },
) {
  if (mutation.options.onError) return;
  if (mutation.meta?.erreurAffichee) return;
  if (axios.isCancel(error)) return;
  toast({
    variant: 'destructive',
    title: TITRE_ECHEC_MUTATION,
    description: getUserErrorMessage(error),
  });
}

export function createAppQueryClient() {
  const queryClient = new QueryClient({
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => {
        signalerEchecDeMutation(error, mutation);
      },
    }),
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
