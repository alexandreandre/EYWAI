import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * Lyon, 17/11 (LEWIS, octobre) : au forfait jours, l'activité partielle posée
 * au calendrier n'était pas calculée. Lecture seule : le récapitulatif du mois
 * compte les jours chômés du forfait (7 h par jour) comme ceux d'un salarié en
 * heures, et le choix existe au calendrier d'un forfait jours. Aucune écriture.
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
  const soc = societes.find((c) => /^lewis/i.test(c.company_name ?? ''));
  expect(soc, 'LEWIS dans le compte QA').toBeTruthy();
  await page.evaluate((id) => {
    localStorage.setItem('activeCompanyId', id);
    localStorage.removeItem('martine-rq-cache-v2');
  }, soc!.company_id);
}

async function recapitulatifDOctobre(page: Page) {
  await page.goto('/suivi-temps-travail');
  await page.getByRole('tab', { name: /Activité partielle/ }).click({ timeout: 30_000 });
  await expect(page.getByTestId('ap-consigne')).toBeVisible({ timeout: 20_000 });
  const listes = page.getByRole('combobox');
  await listes.nth(0).click();
  await page.getByRole('option', { name: '2026' }).click();
  await listes.nth(1).click();
  await page.getByRole('option', { name: /^octobre$/i }).click();

  // Un forfait jours avec ses jours chômés au calendrier : 2 jours, 14 h.
  const forfait = page.getByRole('row').filter({ hasText: 'forfait jours, 7 h par jour' }).filter({ hasText: /\d+ j · \d+ h/ });
  await expect(forfait.first()).toBeVisible({ timeout: 30_000 });
  await expect(forfait.first().getByTestId('ap-calendrier')).toContainText('2 j · 14 h');
  await expect(forfait.first().getByTestId('ap-calendrier')).toContainText(/retenue .*€ · indemnité .*€/);
  // Des salariés en heures dans le même tableau.
  await expect(page.getByRole('row').filter({ hasNotText: 'forfait jours' }).nth(1)).toBeVisible();
}

async function choixAuCalendrierDuForfait(page: Page) {
  const liste = (await (
    await page.request.get(`${API_URL}/api/employees/summary`, { headers: await entetes(page) })
  ).json()) as { id: string; is_forfait_jour?: boolean }[];
  const f = liste.find((x) => x.is_forfait_jour);
  expect(f, 'un forfait jours chez LEWIS').toBeTruthy();
  await page.goto(`/employees/${f!.id}?tab=calendrier`);
  await expect(page.getByRole('button', { name: /Importer un relevé/ })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText("Cette page n'a pas pu s'afficher")).toHaveCount(0);
}

test('activité partielle au forfait jours (LEWIS, octobre) : comptée comme en heures', async ({ page }) => {
  test.setTimeout(240_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);
  await choisirLewis(page);
  await test.step('récapitulatif d’octobre : forfait jours à 7 h par jour chômé', () => recapitulatifDOctobre(page));
  await test.step('calendrier d’un forfait jours', () => choixAuCalendrierDuForfait(page));
  await verifierPageSaine(page, s);
});
