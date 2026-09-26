/**
 * Cache React Query persisté dans le localStorage (24 h).
 *
 * Ce cache porte les données d'un utilisateur dans une société, alors que
 * beaucoup de clés de requête n'ont pas l'identifiant de société. Au
 * changement de société ou d'utilisateur, le rechargement partait avant la
 * sauvegarde différée (1 s) du persister : l'ancien cache était restauré et
 * jugé frais — la donnée de la société A s'affichait dans la société B
 * (constat C3 de l'audit du 25/09). Deux protections :
 * - `purgePersistedQueryCache` supprime le cache persisté synchronement, avant
 *   le rechargement ou la redirection ;
 * - `readQueryCacheBuster` date le cache par build, utilisateur et société
 *   active lus au démarrage : un cache écrit pour un autre couple
 *   utilisateur/société est jeté à la restauration.
 */

import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';
import { getAccessTokenSubject } from '@/lib/authSession';
import { QUERY_CACHE_BUSTER, QUERY_CACHE_KEY } from '@/lib/queryClient';

/** Clé de la société active, écrite par CompanyContext. */
const ACTIVE_COMPANY_STORAGE_KEY = 'activeCompanyId';

type CacheStorage = {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
  removeItem: (key: string) => void;
};

/**
 * Vrai après une purge annonçant un départ de la page : la sauvegarde différée
 * ne doit plus réécrire le cache entre la purge et le rechargement.
 */
let writesSuspended = false;

function browserStorage(): CacheStorage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

/** Persister de l'application : celui de React Query, dont on peut suspendre les écritures. */
export function createAppQueryPersister() {
  const storage = browserStorage();
  return createSyncStoragePersister({
    storage: storage && {
      getItem: (key) => storage.getItem(key),
      setItem: (key, value) => {
        if (!writesSuspended) storage.setItem(key, value);
      },
      removeItem: (key) => storage.removeItem(key),
    },
    key: QUERY_CACHE_KEY,
  });
}

/**
 * Supprime synchronement le cache persisté.
 *
 * `beforeLeaving` : la page va être rechargée ou quittée. Les écritures du
 * persister sont alors suspendues jusqu'au départ, pour que la sauvegarde
 * différée ne remette pas en place un cache de l'ancienne société ou de
 * l'ancien utilisateur.
 */
export function purgePersistedQueryCache({ beforeLeaving = false } = {}): void {
  if (beforeLeaving) writesSuspended = true;
  try {
    browserStorage()?.removeItem(QUERY_CACHE_KEY);
  } catch {
    /* stockage indisponible : il n'y a rien à purger */
  }
}

/**
 * `buster` du cache persisté : un cache écrit pour un autre build, un autre
 * utilisateur ou une autre société active ne correspond plus et est jeté.
 */
export function buildQueryCacheBuster({
  build = QUERY_CACHE_BUSTER,
  userId,
  companyId,
}: {
  build?: string;
  userId: string | null;
  companyId: string | null;
}): string {
  return `${build}|utilisateur:${userId ?? 'aucun'}|societe:${companyId ?? 'aucune'}`;
}

/** `buster` du démarrage, d'après le jeton et la société active mémorisés. */
export function readQueryCacheBuster(): string {
  let companyId: string | null = null;
  let userId: string | null = null;
  try {
    companyId = browserStorage()?.getItem(ACTIVE_COMPANY_STORAGE_KEY) || null;
    userId = getAccessTokenSubject();
  } catch {
    /* stockage indisponible : le persister n'aura rien à restaurer non plus */
  }
  return buildQueryCacheBuster({ userId, companyId });
}
