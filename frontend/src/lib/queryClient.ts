import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';
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

/** Ce qu'une lecture peut dire au filet global d'erreurs. */
export type MetaDeLecture = {
  /** L'écran affiche déjà l'échec de cette lecture : le filet se tait. */
  erreurAffichee?: boolean;
};

declare module '@tanstack/react-query' {
  interface Register {
    mutationMeta: MetaDeMutation;
    queryMeta: MetaDeLecture;
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

export const TITRE_ECHEC_LECTURE = 'Données non chargées';

/** Statuts qu'une lecture rend sans panne : session, droits, donnée absente. */
const LECTURE_SANS_PANNE = new Set([401, 403, 404]);

/**
 * Une lecture qui échoue ne doit pas laisser un écran vide qui dit « Aucun… »
 * (audit du 17/11). Le filet ne parle que si : rien n'est affiché (pas de
 * donnée plus ancienne), un écran regarde cette donnée (pas un préchargement),
 * et c'est une vraie panne (pas 401, 403, 404, ni une annulation).
 */
export function doitSignalerEchecDeLecture(
  error: unknown,
  query: { state: { data: unknown }; meta?: MetaDeLecture; getObserversCount: () => number },
): boolean {
  if (query.meta?.erreurAffichee) return false;
  if (query.state.data !== undefined) return false;
  if (query.getObserversCount() === 0) return false;
  if (axios.isCancel(error)) return false;
  const status = axios.isAxiosError(error) ? error.response?.status : undefined;
  if (status !== undefined && LECTURE_SANS_PANNE.has(status)) return false;
  return true;
}

export function createAppQueryClient() {
  const queryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (!doitSignalerEchecDeLecture(error, query)) return;
        toast({
          variant: 'destructive',
          title: TITRE_ECHEC_LECTURE,
          description: `${getUserErrorMessage(error)} Rechargez la page ; ce qui s'affiche peut être incomplet.`,
        });
      },
    }),
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
