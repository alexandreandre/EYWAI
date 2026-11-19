import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * Défauts restants après Lyon (18/11), rejoués à l'écran sans rien enregistrer
 * (la garde bloque toute écriture) :
 * - A5 : des heures saisies en groupe sans type laissent un congé tel quel, et
 *   le message dit combien de jours ont été laissés ;
 * - A6 : un congé repassé en « Travail » reprend les heures prévues du modèle
 *   de semaine (il restait à 0 h prévue).
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

/** La case d'un jour du calendrier, retrouvée par sa case à cocher. */
function caseDuJour(page: Page, jour: number) {
  return page
    .getByLabel(`Sélectionner le jour ${jour}`, { exact: true })
    .locator('xpath=ancestor::div[contains(@class,"group")][1]');
}

function typeDuJour(page: Page, jour: number) {
  return caseDuJour(page, jour).locator('button.text-\\[10px\\]').first();
}

async function prevuDuJour(page: Page, jour: number): Promise<number> {
  const texte = (await caseDuJour(page, jour).innerText()).replace(/\s+/g, ' ');
  const m = texte.match(/PRÉVU ([\d,]+) ?h/i);
  return m ? Number(m[1].replace(',', '.')) : 0;
}

test('saisie groupée sans type et retour en Travail (A5, A6), sans enregistrer', async ({ page }) => {
  test.setTimeout(240_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);

  await choisirSociete(page, /mont[\s-]?blanc/i);
  await page.goto(`/employees/${await unSalarieEnHeures(page)}?tab=calendrier`);
  await expect(page.getByRole('button', { name: /Importer un relevé/ })).toBeVisible({ timeout: 45_000 });
  // Les cases arrivent après le bouton : sans cette attente, le parcours ne
  // trouvait aucun jour (19/11, calendrier encore en chargement).
  await expect(page.getByLabel('Sélectionner le jour 1', { exact: true })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText(/^Prévu$/i).first()).toBeVisible({ timeout: 45_000 });

  // Deux jours « Travail » du mois affiché, avec des heures prévues.
  const jours: number[] = [];
  for (let j = 1; j <= 28 && jours.length < 2; j++) {
    if ((await caseDuJour(page, j).count()) === 0) continue;
    if ((await typeDuJour(page, j).innerText()).trim() !== 'Travail') continue;
    if ((await prevuDuJour(page, j)) > 0) jours.push(j);
  }
  expect(jours, 'deux jours « Travail » avec un prévu').toHaveLength(2);
  const [conge, travail] = jours;

  // Le premier passe en congé payé, à l'écran seulement.
  await typeDuJour(page, conge).click();
  await page.getByRole('dialog').last().getByRole('button', { name: 'Congés payés', exact: true }).click();
  await expect(typeDuJour(page, conge)).toHaveText(/Congés payés/);

  // A5 : 5 h faites sur les deux jours, sans type.
  await page.getByLabel(`Sélectionner le jour ${conge}`, { exact: true }).click();
  await page.getByLabel(`Sélectionner le jour ${travail}`, { exact: true }).click();
  await page.locator('#bulk-actual-hours').fill('5');
  await page.getByRole('button', { name: 'Appliquer', exact: true }).click();
  await expect(page.getByText(/1 jour modifié\. 1 jour garde son type/).first()).toBeVisible();
  await expect(typeDuJour(page, conge)).toHaveText(/Congés payés/);
  await expect(typeDuJour(page, travail)).toHaveText(/^Travail/);

  // A6 : le congé repassé en « Travail » reprend les heures du modèle.
  await typeDuJour(page, conge).click();
  await page.getByRole('dialog').last().getByRole('button', { name: 'Travail', exact: true }).click();
  await expect(typeDuJour(page, conge)).toHaveText(/^Travail/);
  await expect.poll(() => prevuDuJour(page, conge)).toBeGreaterThan(0);

  await verifierPageSaine(page, s);
});
