import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * L19 (27/11) : « Primes du mois » dit les jours travaillés sans heure
 * d'arrivée que les règles de panier ne comptent pas. Lecture seule : on ouvre
 * octobre chez LEWIS, l'encadré ne doit jamais rester muet ni bloqué sur
 * « Vérification… », et la route répond la même chose que l'écran.
 */
async function entetes(page: Page) {
  const { jeton, societe } = await page.evaluate(() => ({
    jeton: localStorage.getItem('authToken'),
    societe: localStorage.getItem('activeCompanyId'),
  }));
  return { Authorization: `Bearer ${jeton}`, ...(societe ? { 'X-Active-Company': societe } : {}) };
}

async function choisirLewis(page: Page) {
  await page.goto('/');
  const societes = (await (
    await page.request.get(`${API_URL}/api/users/my-companies`, { headers: await entetes(page) })
  ).json()) as { company_id: string; company_name?: string }[];
  const soc = societes.find((c) => /lewis/i.test(c.company_name ?? ''));
  expect(soc, 'LEWIS dans les sociétés du compte QA').toBeTruthy();
  await page.evaluate((id) => {
    localStorage.setItem('activeCompanyId', id);
    localStorage.removeItem('martine-rq-cache-v2');
  }, soc!.company_id);
  return soc!.company_id;
}

test('Primes du mois : jours sans heure d’arrivée dits, jamais muets', async ({ page }) => {
  test.setTimeout(240_000);
  const s = surveiller(page);
  const societe = await choisirLewis(page);

  const reponse = await page.request.get(
    `${API_URL}/api/payroll-variables/jours-sans-heure-d-arrivee?year=2026&month=10&company_id=${societe}`,
    { headers: await entetes(page), timeout: 180_000 },
  );
  expect(reponse.status()).toBe(200);
  const lignes = (await reponse.json()) as { employee_id: string }[];
  expect(Array.isArray(lignes)).toBe(true);

  const lectureDeLEcran = page.waitForResponse(
    (r) => r.url().includes('/jours-sans-heure-d-arrivee') && r.url().includes('month=10'),
    { timeout: 180_000 },
  );
  await page.goto('/saisies?month=2026-10');
  await expect(page.getByText('Saisies enregistrées')).toBeVisible({ timeout: 30_000 });
  expect((await lectureDeLEcran).status()).toBe(200);

  // La lecture finit : plus de « Vérification… », ni d'échec de lecture.
  await expect(page.getByText("Vérification des heures d'arrivée…")).toHaveCount(0, { timeout: 180_000 });
  await expect(page.getByText(/n'ont pas pu être relus au calendrier/)).toHaveCount(0);

  // L'écran dit ce que la route dit : la liste quand il y a des jours, rien sinon.
  if (lignes.length > 0) {
    const encadre = page.getByTestId('jours-sans-arrivee');
    await expect(encadre).toBeVisible();
    await expect(encadre).toContainText(/sans heure d'arrivée/);
  } else {
    await expect(page.getByTestId('jours-sans-arrivee')).toHaveCount(0);
  }

  await verifierPageSaine(page, s);
});
