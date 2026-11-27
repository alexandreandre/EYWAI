import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * L17-C (retour d'Elsa) : « quand on descend dans le calendrier, que le bandeau
 * du haut avec les jours soit visible ».
 *
 * Vue Planning : on descend dans la grille (molette), la ligne des jours reste
 * collée en haut du cadre. Calendrier du mois d'un salarié (fiche) : on descend
 * dans la page, la ligne « Lun … Dim » reste en haut. Lecture seule.
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

test('l’en-tête des jours reste visible quand on descend (Planning et calendrier du mois)', async ({ page }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1280, height: 700 });
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);

  // LEWIS : assez de salariés pour que la grille défile.
  await choisirSociete(page, /^lewis/i);
  await page.goto('/schedules');
  const grille = page.getByTestId('grille-planning');
  await expect(grille).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole('button', { name: /^Éditer le \d+ pour / }).first()).toBeVisible({ timeout: 60_000 });
  const entete = page.getByTestId('entete-jour').first();
  const hautGrille = (await grille.boundingBox())!.y;

  await grille.hover();
  await page.mouse.wheel(0, 1500);
  await expect.poll(() => grille.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  const apres = (await entete.boundingBox())!;
  expect(Math.abs(apres.y - hautGrille), 'la ligne des jours reste en haut du cadre').toBeLessThan(4);
  await expect(entete).toBeInViewport();

  // Calendrier du mois d'un salarié (fiche).
  const liste = (await (
    await page.request.get(`${API_URL}/api/employees/summary`, { headers: await entetes(page) })
  ).json()) as { id: string; is_forfait_jour?: boolean }[];
  const salarie = liste.find((x) => !x.is_forfait_jour) ?? liste[0];
  await page.goto(`/employees/${salarie.id}?tab=calendrier`);
  const jours = page.getByTestId('entete-jours-du-mois');
  await expect(jours).toBeVisible({ timeout: 60_000 });
  await expect(page.getByLabel('Sélectionner le jour 1', { exact: true })).toBeVisible({ timeout: 60_000 });
  await page.getByLabel('Sélectionner le jour 28', { exact: true }).scrollIntoViewIfNeeded();
  await page.mouse.wheel(0, 400);
  await expect(jours).toBeInViewport();
  await expect(jours).toContainText('Lun');
  await verifierPageSaine(page, s);
});
