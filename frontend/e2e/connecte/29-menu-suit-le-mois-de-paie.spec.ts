import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * Retour du 26/11 (LEWIS) : Elsa fait la paie d'octobre, le menu comptait
 * « Calendrier · novembre ». Le mois choisi dans « Générer la Paie » est
 * retenu pour la société : le menu le suit, la fenêtre s'y rouvre.
 * Lecture seule : rien n'est généré.
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

test('le mois choisi pour la paie de LEWIS est suivi par le menu', async ({ page }) => {
  test.setTimeout(240_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);
  await choisirSociete(page, /^lewis/i);
  await page.goto('/payroll/generate');
  await page.locator('#month-select').click({ timeout: 45_000 });
  await page.getByRole('option', { name: /octobre 2026/i }).click();
  await expect(page.locator('#month-select')).toContainText(/octobre 2026/i);

  // Le menu compte les calendriers d'octobre (LEWIS en a à saisir en octobre).
  await expect(page.getByRole('link', { name: /Calendrier · octobre/i }).first()).toBeVisible({
    timeout: 120_000,
  });
  await expect(page.getByRole('link', { name: /Calendrier · novembre/i })).toHaveCount(0);

  // Rouverte, la fenêtre reprend octobre.
  await page.goto('/payroll/generate');
  await expect(page.locator('#month-select')).toContainText(/octobre 2026/i, { timeout: 45_000 });
  await verifierPageSaine(page, s);
});
