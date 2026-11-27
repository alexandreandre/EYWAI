import { test as base, expect } from '@playwright/test';
import { ETAT_AUTH } from './env';

/**
 * Garde anti-écriture des specs « connecté ».
 *
 * Le site de test porte la vraie paie de clients : aucun test ne doit y
 * écrire. Cette garde est installée AVANT tout test (fixture automatique) :
 * toute requête d'écriture (POST, PUT, PATCH, DELETE) vers l'API que le test
 * n'a pas simulée avec `page.route` (et traitée par `route.fulfill`) est
 * BLOQUÉE avant de partir, puis fait échouer le test.
 *
 * Les routes d'un test sont évaluées avant la garde (la dernière enregistrée
 * passe en premier) : une simulation qui répond n'atteint jamais la garde ; une
 * simulation qui appelle `route.fallback()` pour une écriture, si.
 *
 * Exceptions, qui ne touchent à aucune donnée métier : la session (/api/auth/)
 * et le journal d'erreurs d'écran (/api/client-errors).
 */
const LECTURES = new Set(['GET', 'HEAD', 'OPTIONS']);

export function ecritureTolerable(chemin: string): boolean {
  return chemin.startsWith('/api/auth/') || chemin.startsWith('/api/client-errors');
}

export const test = base.extend<{ gardeEcritures: string[] }>({
  gardeEcritures: [
    async ({ page }, use) => {
      const bloquees: string[] = [];
      await page.route(/\/api\//, async (route) => {
        const requete = route.request();
        const { pathname } = new URL(requete.url());
        if (LECTURES.has(requete.method()) || ecritureTolerable(pathname)) {
          return route.fallback();
        }
        bloquees.push(`${requete.method()} ${pathname}`);
        await route.abort('blockedbyclient');
      });
      await use(bloquees);
      await reporterLaSession(page);
      expect(bloquees, 'écritures non simulées, bloquées par la garde').toEqual([]);
    },
    { auto: true },
  ],
});

/**
 * Le jeton de renouvellement change à chaque usage (rotation) : si un test a
 * renouvelé la session, les suivants, repartis du fichier d'origine, en
 * présenteraient un périmé (401 sur /api/auth/refresh, puis session effacée).
 * On reporte donc la session à jour dans le fichier, test après test
 * (workers: 1). Une session effacée n'est jamais reportée.
 */
async function reporterLaSession(page: import('@playwright/test').Page) {
  try {
    if (!page.url().startsWith('http')) return;
    const encoreConnecte = await page.evaluate(
      () => !!window.localStorage.getItem('authToken') && !!window.localStorage.getItem('refreshToken'),
    );
    if (encoreConnecte) await page.context().storageState({ path: ETAT_AUTH });
  } catch {
    // page fermée ou navigation en cours : on garde le fichier tel quel.
  }
}

export { expect };
