import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import {
  persistQueryClientRestore,
  persistQueryClientSave,
} from '@tanstack/react-query-persist-client';
import type { QueryKey } from '@tanstack/react-query';
import { QUERY_CACHE_KEY } from '@/lib/queryClient';
import { queryKeys } from '@/lib/queryKeys';

type Module = typeof import('@/lib/queryCachePersistence');

/** Jeton d'accès factice : seul le `sub` compte ici. */
function jeton(sub: string): string {
  const payload = btoa(JSON.stringify({ sub, exp: 4102444800 }))
    .replace(/=+$/, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
  return `entete.${payload}.signature`;
}

let store: Map<string, string>;
let mod: Module;

beforeEach(async () => {
  store = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
  });
  vi.useFakeTimers();
  // Module neuf à chaque test : la suspension des écritures est un état de page.
  vi.resetModules();
  mod = await import('@/lib/queryCachePersistence');
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** Sauvegarde le cache comme le fait PersistQueryClientProvider (écriture différée d'1 s). */
async function sauvegarder(queryClient: QueryClient, persister: ReturnType<Module['createAppQueryPersister']>) {
  await persistQueryClientSave({ queryClient, persister, buster: mod.readQueryCacheBuster() });
  vi.advanceTimersByTime(1000);
}

describe('buildQueryCacheBuster', () => {
  it('change avec l’utilisateur, la société active et le build', () => {
    const base = mod.buildQueryCacheBuster({ build: 'b1', userId: 'u1', companyId: 'c1' });
    expect(mod.buildQueryCacheBuster({ build: 'b1', userId: 'u1', companyId: 'c1' })).toBe(base);
    expect(mod.buildQueryCacheBuster({ build: 'b1', userId: 'u2', companyId: 'c1' })).not.toBe(base);
    expect(mod.buildQueryCacheBuster({ build: 'b1', userId: 'u1', companyId: 'c2' })).not.toBe(base);
    expect(mod.buildQueryCacheBuster({ build: 'b2', userId: 'u1', companyId: 'c1' })).not.toBe(base);
  });

  it('distingue l’absence d’utilisateur ou de société', () => {
    const anonyme = mod.buildQueryCacheBuster({ build: 'b1', userId: null, companyId: null });
    expect(anonyme).not.toBe(mod.buildQueryCacheBuster({ build: 'b1', userId: 'u1', companyId: null }));
    expect(anonyme).not.toBe(mod.buildQueryCacheBuster({ build: 'b1', userId: null, companyId: 'c1' }));
  });
});

describe('readQueryCacheBuster', () => {
  it('lit l’utilisateur du jeton et la société active mémorisée', () => {
    store.set('authToken', jeton('utilisateur-1'));
    store.set('activeCompanyId', 'societe-a');
    expect(mod.readQueryCacheBuster()).toBe(
      mod.buildQueryCacheBuster({ userId: 'utilisateur-1', companyId: 'societe-a' }),
    );
  });

  it('reste lisible sans jeton ou avec un jeton illisible', () => {
    store.set('activeCompanyId', 'societe-a');
    const sansJeton = mod.readQueryCacheBuster();
    expect(sansJeton).toBe(mod.buildQueryCacheBuster({ userId: null, companyId: 'societe-a' }));
    store.set('authToken', 'pas-un-jwt');
    expect(mod.readQueryCacheBuster()).toBe(sansJeton);
  });
});

describe('cache persisté et changement de société', () => {
  it('un cache écrit pour la société A n’est pas restauré dans la société B', async () => {
    store.set('authToken', jeton('utilisateur-1'));
    store.set('activeCompanyId', 'societe-a');
    const avant = new QueryClient();
    avant.setQueryData(['employees'], ['salarié de A']);
    await sauvegarder(avant, mod.createAppQueryPersister());
    expect(store.has(QUERY_CACHE_KEY)).toBe(true);

    // Rechargement dans la société B, sans purge : le buster suffit à rejeter l'ancien cache.
    store.set('activeCompanyId', 'societe-b');
    const apres = new QueryClient();
    await persistQueryClientRestore({
      queryClient: apres,
      persister: mod.createAppQueryPersister(),
      buster: mod.readQueryCacheBuster(),
    });
    expect(apres.getQueryData(['employees'])).toBeUndefined();
    expect(store.has(QUERY_CACHE_KEY)).toBe(false);
  });

  it('un cache de la même société et du même utilisateur est restauré comme avant', async () => {
    store.set('authToken', jeton('utilisateur-1'));
    store.set('activeCompanyId', 'societe-a');
    const avant = new QueryClient();
    avant.setQueryData(['employees'], ['salarié de A']);
    await sauvegarder(avant, mod.createAppQueryPersister());

    const apres = new QueryClient();
    await persistQueryClientRestore({
      queryClient: apres,
      persister: mod.createAppQueryPersister(),
      buster: mod.readQueryCacheBuster(),
    });
    expect(apres.getQueryData(['employees'])).toEqual(['salarié de A']);
  });

  it('un autre utilisateur de la même société ne reprend pas le cache', async () => {
    store.set('authToken', jeton('utilisateur-1'));
    store.set('activeCompanyId', 'societe-a');
    const avant = new QueryClient();
    avant.setQueryData(['employees'], ['salarié de A']);
    await sauvegarder(avant, mod.createAppQueryPersister());

    store.set('authToken', jeton('utilisateur-2'));
    const apres = new QueryClient();
    await persistQueryClientRestore({
      queryClient: apres,
      persister: mod.createAppQueryPersister(),
      buster: mod.readQueryCacheBuster(),
    });
    expect(apres.getQueryData(['employees'])).toBeUndefined();
  });
});

describe('purgePersistedQueryCache', () => {
  it('supprime le cache persisté tout de suite, sans toucher à la session', () => {
    store.set(QUERY_CACHE_KEY, '{"buster":"x"}');
    store.set('authToken', jeton('utilisateur-1'));
    store.set('activeCompanyId', 'societe-a');
    mod.purgePersistedQueryCache();
    expect(store.has(QUERY_CACHE_KEY)).toBe(false);
    expect(store.get('activeCompanyId')).toBe('societe-a');
    expect(store.has('authToken')).toBe(true);
  });

  it('avant un départ, la sauvegarde différée ne réécrit plus l’ancien cache', async () => {
    const persister = mod.createAppQueryPersister();
    const client = new QueryClient();
    client.setQueryData(['employees'], ['salarié de A']);
    // Sauvegarde programmée (1 s) juste avant le changement de société…
    await persistQueryClientSave({ queryClient: client, persister, buster: 'b' });
    mod.purgePersistedQueryCache({ beforeLeaving: true });
    // … elle tombe avant que la page soit partie : rien n'est réécrit.
    vi.advanceTimersByTime(1000);
    expect(store.has(QUERY_CACHE_KEY)).toBe(false);
  });

  it('sans départ (connexion), le cache continue de se sauvegarder ensuite', async () => {
    const persister = mod.createAppQueryPersister();
    mod.purgePersistedQueryCache();
    const client = new QueryClient();
    client.setQueryData(['employees'], ['salarié']);
    await persistQueryClientSave({ queryClient: client, persister, buster: 'b' });
    vi.advanceTimersByTime(1000);
    expect(store.has(QUERY_CACHE_KEY)).toBe(true);
  });

  it('ne casse rien si le stockage est indisponible', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('stockage bloqué');
      },
      setItem: () => {
        throw new Error('stockage bloqué');
      },
      removeItem: () => {
        throw new Error('stockage bloqué');
      },
    });
    expect(() => mod.purgePersistedQueryCache({ beforeLeaving: true })).not.toThrow();
    expect(() => mod.readQueryCacheBuster()).not.toThrow();
    expect(() => mod.createAppQueryPersister()).not.toThrow();
  });
});

/** Clés écrites dans le cache persisté, telles que les relira le prochain démarrage. */
function clesPersistees(): QueryKey[] {
  const brut = store.get(QUERY_CACHE_KEY);
  if (!brut) return [];
  const cache = JSON.parse(brut) as { clientState: { queries: { queryKey: QueryKey }[] } };
  return cache.clientState.queries.map((q) => q.queryKey);
}

async function persister(client: QueryClient) {
  await persistQueryClientSave({
    queryClient: client,
    persister: mod.createAppQueryPersister(),
    buster: 'b',
    dehydrateOptions: mod.appDehydrateOptions,
  });
  vi.advanceTimersByTime(1000);
}

describe('requêtes de la paie : jamais persistées', () => {
  // Le 29/09, la liste des bulletins restaurée du cache de 24 h montrait des
  // bulletins déjà supprimés ou remplacés : l'écran ne disait pas qu'elle était périmée.
  const NON_PERSISTEES: Record<string, QueryKey> = {
    'bulletins du salarié (paie, fiche)': queryKeys.employeePayslips('co-1', 'e1'),
    'mes bulletins (espace salarié)': [...queryKeys.employeeDashboard('u1'), 'payslips'],
    'comparaison d’un bulletin': queryKeys.payslipComparison('ps-1'),
    'tendance d’un bulletin': queryKeys.payslipTrend('ps-1'),
    'anomalies des bulletins': queryKeys.payslipsAnomalies('co-1', 2026, 9),
    'contrôle avant paie': queryKeys.payrollPreflight('co-1', 2026, 9),
    'fenêtre des variables du mois': queryKeys.periodeVariables('co-1', 2026, 9),
    'salariés de la paie': [...queryKeys.employees('co-1'), 'payroll'],
    'heures de la semaine': ['employee-week-payroll', 'e1', '2026-09-07', false, ''],
    'calendrier des absences': ['employee-absences-calendar', 'e1'],
    'planning de la semaine': queryKeys.planningWeek('co-1', '2026-09-07'),
    'planning du mois': ['planning-month', 'co-1', 2026, 9],
    'mon planning': ['my-planning', '2026-09-07', 'co-1'],
  };
  const PERSISTEES: Record<string, QueryKey> = {
    'liste des salariés': queryKeys.employees('co-1'),
    'paramètres de la société': queryKeys.companySettings('co-1'),
    'mes sociétés': queryKeys.myCompanies(),
  };

  it.each(Object.entries(NON_PERSISTEES))('%s : non écrite', async (_nom, key) => {
    const client = new QueryClient();
    client.setQueryData(key, 'donnée');
    client.setQueryData(queryKeys.employees('co-1'), ['salarié']);

    await persister(client);

    expect(clesPersistees()).not.toContainEqual(key);
    expect(clesPersistees()).toContainEqual(queryKeys.employees('co-1'));
  });

  it.each(Object.entries(PERSISTEES))('%s : toujours persistée', async (_nom, key) => {
    const client = new QueryClient();
    client.setQueryData(key, 'donnée');

    await persister(client);

    expect(clesPersistees()).toContainEqual(key);
  });

  it('les données sensibles restent exclues', async () => {
    const client = new QueryClient();
    client.setQueryData(['employee', 'e1', 'sensitive', 'rib'], 'FR76…');

    await persister(client);

    expect(clesPersistees()).toEqual([]);
  });

  it('isPersistableQueryKey : la règle seule, sans React Query', () => {
    for (const key of Object.values(NON_PERSISTEES)) {
      expect(mod.isPersistableQueryKey(key), JSON.stringify(key)).toBe(false);
    }
    for (const key of Object.values(PERSISTEES)) {
      expect(mod.isPersistableQueryKey(key), JSON.stringify(key)).toBe(true);
    }
  });
});

describe('version du cache persisté', () => {
  it('passe à v2 : le cache v1 gardait les bulletins 24 h', () => {
    expect(QUERY_CACHE_KEY).toBe('eywai-rq-cache-v2');
  });

  it('le cache v1 laissé par l’ancienne version est jeté au démarrage', () => {
    store.set('eywai-rq-cache-v1', '{"buster":"x","clientState":{"queries":[]}}');
    store.set('activeCompanyId', 'societe-a');

    mod.createAppQueryPersister();

    expect(store.has('eywai-rq-cache-v1')).toBe(false);
    expect(store.get('activeCompanyId')).toBe('societe-a');
  });
});
