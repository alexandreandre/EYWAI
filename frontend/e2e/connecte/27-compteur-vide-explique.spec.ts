import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * Compteur de récupération vide (retour du 26/11, LEWIS) : les heures sup
 * « mises au compteur » n'y passent qu'au calcul du bulletin. L'écran le dit,
 * et un salarié sans mouvement n'a plus un « — » muet ni un tableau vide.
 * Lecture seule : la garde bloque toute écriture.
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

test('compteur de récupération : l’écran dit quand il se remplit (LEWIS)', async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);
  await choisirSociete(page, /^lewis/i);
  await page.goto('/suivi-temps-travail?tab=compte-heures');

  await expect(page.getByTestId('compteur-quand')).toContainText(
    'Le compteur se remplit au calcul du bulletin',
    { timeout: 45_000 },
  );

  // Un salarié sans mouvement : « 0.00 (aucun mouvement) », puis un détail qui le dit.
  const ligne = page.locator('tbody tr', { hasText: '0.00 (aucun mouvement)' }).first();
  await expect(ligne, 'LEWIS a des salariés sans mouvement au compteur').toBeVisible({ timeout: 45_000 });
  await ligne.getByRole('button', { name: 'Détail du compteur', exact: true }).click();
  await expect(page.getByTestId('compteur-vide')).toContainText(
    'passeront au compteur au calcul de son prochain bulletin',
    { timeout: 30_000 },
  );
  await verifierPageSaine(page, s);
});
