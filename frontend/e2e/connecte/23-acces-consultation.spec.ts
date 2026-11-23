import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

// L'écran d'un compte en consultation (expert-comptable) : rôle rh, pas
// administrateur plateforme, accès marqués « consultation ». Le compte QA est
// administrateur plateforme ; on le fait passer pour ce compte en réécrivant
// /api/auth/me. Le serveur garde les droits du compte QA : ses refus sont
// simulés ici avec le message du vrai serveur (testé à part dans
// backend/tests/unit/core/test_acces_en_consultation.py).
//
// Ce qu'on vérifie : le bandeau est sur chaque page de paie, ces pages se
// chargent sans erreur, et aucune ne tente de modifier quoi que ce soit en
// s'ouvrant (hors lectures envoyées en POST, que le serveur laisse passer).

const MESSAGE = 'Accès en consultation : vous pouvez tout voir, mais rien modifier.';

type Acces = Record<string, unknown> | null | undefined;

async function commeUnCompteEnConsultation(page: Page) {
  await page.route('**/api/auth/me', async (route) => {
    const reponse = await route.fetch();
    const moi = await reponse.json();
    const enConsultation = (acces: Acces) => (acces ? { ...acces, role: 'rh', lecture_seule: true } : acces);
    await route.fulfill({
      response: reponse,
      json: {
        ...moi,
        is_platform_admin: false,
        is_super_admin: false,
        role: 'rh',
        consultation: true,
        active_company: enConsultation(moi.active_company),
        accessible_companies: (moi.accessible_companies ?? []).map(enConsultation),
      },
    });
  });
}

/** Lectures envoyées en POST, que le serveur laisse passer en consultation. */
function lecturePermise(methode: string, url: URL): boolean {
  const chemin = url.pathname;
  if (methode !== 'POST') return false;
  if (chemin === '/api/exports/preview') return true;
  if (/^\/api\/simulation\/(arret-maladie|reverse-calculation|[^/]+\/compare)$/.test(chemin)) return true;
  return chemin === '/api/payroll-variables/generate' && url.searchParams.get('dry_run') === 'true';
}

async function refuserCommeLeServeur(page: Page) {
  const refusees: string[] = [];
  await page.route(/\/api\//, async (route) => {
    const requete = route.request();
    const url = new URL(requete.url());
    if (['GET', 'HEAD', 'OPTIONS'].includes(requete.method())) return route.fallback();
    if (url.pathname.startsWith('/api/auth/') || url.pathname.startsWith('/api/client-errors')) {
      return route.fallback();
    }
    if (lecturePermise(requete.method(), url)) {
      // Lecture pure : l'appel part au vrai serveur.
      return route.fulfill({ response: await route.fetch() });
    }
    refusees.push(`${requete.method()} ${url.pathname}`);
    await route.fulfill({ status: 403, json: { detail: MESSAGE } });
  });
  return refusees;
}

// Session neuve : la réponse réécrite de /api/auth/me doit être lue dès la connexion.
test.use({ storageState: { cookies: [], origins: [] } });

async function seConnecter(page: Page) {
  await page.goto('/login');
  await page.locator('#login-username').fill(process.env.E2E_QA_EMAIL!);
  await page.locator('#login-password').fill(process.env.E2E_QA_PASSWORD!);
  await page.getByRole('button', { name: /se connecter/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 30_000 });
}

test('le parcours d’un compte en consultation', async ({ page }) => {
  test.setTimeout(240_000);
  await commeUnCompteEnConsultation(page);
  await page.addInitScript(() => localStorage.removeItem('martine-rq-cache-v2'));
  await seConnecter(page);
  const refusees = await refuserCommeLeServeur(page);
  const s = surveiller(page);

  const pages: Array<[string, RegExp]> = [
    ['/', /./],
    ['/payroll', /gestion de la paie/i],
    ['/exports', /export/i],
    ['/company', /paie|entreprise/i],
    ['/leaves', /cong/i],
    ['/saisies', /saisie|variable/i],
  ];
  for (const [chemin, titre] of pages) {
    await test.step(`${chemin} : bandeau, page saine, rien de modifié à l'ouverture`, async () => {
      const avant = refusees.length;
      await page.goto(chemin);
      await expect(page.getByText(/Accès en consultation\./).first()).toBeVisible({ timeout: 30_000 });
      await expect(page.getByText(titre).first()).toBeVisible({ timeout: 30_000 });
      await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
      expect(refusees.slice(avant), `modifications tentées à l'ouverture de ${chemin}`).toEqual([]);
      await verifierPageSaine(page, s, chemin);
    });
  }
});
