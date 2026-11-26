import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * Retour d'Elsa du 26/11 : une semaine à cheval sur deux mois (S40) obligeait
 * à changer de mois. Les jours des mois voisins s'affichent dans la grille, en
 * lecture, et un clic ouvre leur mois. Aucune écriture.
 */
async function entetes(page: Page) {
  const { jeton, societe } = await page.evaluate(() => ({
    jeton: localStorage.getItem('authToken'),
    societe: localStorage.getItem('activeCompanyId'),
  }));
  return { Authorization: `Bearer ${jeton}`, ...(societe ? { 'X-Active-Company': societe } : {}) };
}

async function choisirSociete(page: Page, nom: RegExp) {
  await page.goto('/');
  const societes = (await (
    await page.request.get(`${API_URL}/api/users/my-companies`, { headers: await entetes(page) })
  ).json()) as { company_id: string; company_name?: string }[];
  const soc = societes.find((c) => nom.test(c.company_name ?? ''));
  expect(soc, `la société ${nom} du compte QA`).toBeTruthy();
  await page.evaluate((id) => {
    localStorage.setItem('activeCompanyId', id);
    localStorage.removeItem('martine-rq-cache-v2');
  }, soc!.company_id);
}

async function unSalarieEnHeures(page: Page): Promise<string> {
  const liste = (await (
    await page.request.get(`${API_URL}/api/employees/summary`, { headers: await entetes(page) })
  ).json()) as { id: string; is_forfait_jour?: boolean; exit_date?: string | null }[];
  const s = liste.find((x) => !x.is_forfait_jour);
  expect(s, 'un salarié en heures').toBeTruthy();
  return s!.id;
}


test('les jours des mois voisins complètent les semaines à cheval', async ({ page }) => {
  test.setTimeout(180_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const ecritures: string[] = [];
  await page.route('**/api/**', async (route) => {
    const req = route.request();
    if (req.method() === 'GET' || req.url().includes('/api/auth/') || req.url().includes('/api/client-errors')) {
      return route.fallback();
    }
    ecritures.push(`${req.method()} ${req.url()}`);
    await route.abort();
  });
  const s = surveiller(page);

  await choisirSociete(page, /mont[\s-]?blanc/i);
  await page.goto(`/employees/${await unSalarieEnHeures(page)}?tab=calendrier`);
  await expect(page.getByLabel('Sélectionner le jour 1', { exact: true })).toBeVisible({ timeout: 45_000 });

  // Le mois affiché : ses jours voisins éventuels sont tous lus (jamais « Chargement… » qui reste).
  const voisins = page.getByTestId('jour-voisin');
  // Remonter jusqu'à un mois qui commence en milieu de semaine (il y en a toujours un sur 2 mois).
  for (let i = 0; i < 2 && (await voisins.count()) === 0; i++) {
    await page.locator('button:has(svg.lucide-chevron-left)').first().click();
    await expect(page.getByLabel('Sélectionner le jour 1', { exact: true })).toBeVisible({ timeout: 45_000 });
  }
  await expect(voisins.first()).toBeVisible();
  await expect(voisins.first()).not.toContainText('Chargement', { timeout: 30_000 });
  await expect(voisins.first()).toContainText(/Prévu|Pas encore enregistré/);
  await expect(voisins.first()).toContainText(/S\d+/);

  // Un clic ouvre le mois du jour voisin : le 1er jour de la grille change.
  const avant = await voisins.first().innerText();
  await voisins.first().click();
  await expect(page.getByLabel('Sélectionner le jour 1', { exact: true })).toBeVisible({ timeout: 45_000 });
  await expect.poll(async () => (await voisins.count()) === 0 || (await voisins.first().innerText()) !== avant).toBe(true);

  expect(ecritures).toEqual([]);
  await verifierPageSaine(page, s);
});
