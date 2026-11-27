import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';
import type { Page } from '@playwright/test';

async function entetes(page: Page) {
  const { jeton, societe } = await page.evaluate(() => ({
    jeton: localStorage.getItem('authToken'),
    societe: localStorage.getItem('activeCompanyId'),
  }));
  return { Authorization: `Bearer ${jeton}`, ...(societe ? { 'X-Active-Company': societe } : {}) };
}

/** Le compte QA (super-admin) voit toutes les sociétés : on fixe LEWIS, qui a des bulletins. */
async function choisirLewis(page: Page) {
  await page.goto('/');
  const societes = (await (
    await page.request.get(`${API_URL}/api/users/my-companies`, { headers: await entetes(page) })
  ).json()) as { company_id: string; company_name?: string }[];
  const soc = societes.find((c) => /^lewis/i.test(c.company_name ?? ''));
  expect(soc, 'la société LEWIS du compte QA').toBeTruthy();
  await page.evaluate((id) => {
    localStorage.setItem('activeCompanyId', id);
    localStorage.removeItem('martine-rq-cache-v2');
  }, soc!.company_id);
}

/**
 * Lot L18 (27/11) : « Fiche individuelle (Excel) » sur la fiche collaborateur,
 * les cumuls mois par mois lus sur les bulletins (utile pour l'indemnité de
 * départ). Lecture seule : le fichier est téléchargé, rien n'est enregistré.
 */
test.describe('Fiche individuelle', () => {
  test('le bouton télécharge la fiche Excel de l’année civile', async ({ page }) => {
    test.setTimeout(120_000);
    const s = surveiller(page);
    await choisirLewis(page);
    await page.goto('/employees');
    // La liste est un tableau à lignes cliquables (pas de liens).
    const ligne = page.getByRole('row').filter({ hasText: /Ancienneté:|Entrée:/ }).first();
    await expect(ligne).toBeVisible({ timeout: 45_000 });
    await ligne.getByRole('cell').first().click();
    await page.waitForURL(/\/employees\/[^/?]+/, { timeout: 30_000 });

    await page.getByRole('button', { name: 'Fiche individuelle (Excel)' }).click({ timeout: 45_000 });
    const fenetre = page.getByRole('dialog');
    await expect(fenetre.getByText('mois non payé dans Martine', { exact: false })).toBeVisible();
    const annee = new Date().getFullYear();
    await expect(fenetre.getByLabel('Premier mois')).toHaveValue(`${annee}-01`);
    await expect(fenetre.getByLabel('Dernier mois')).toHaveValue(`${annee}-12`);

    // Une période à l'envers est refusée avant l'envoi, et l'écran dit pourquoi.
    await fenetre.getByLabel('Premier mois').fill(`${annee}-12`);
    await fenetre.getByLabel('Dernier mois').fill(`${annee}-01`);
    await expect(fenetre.getByText('Le premier mois est après le dernier.')).toBeVisible();
    await expect(fenetre.getByRole('button', { name: 'Télécharger' })).toBeDisabled();

    await fenetre.getByLabel('Premier mois').fill(`${annee}-01`);
    await fenetre.getByLabel('Dernier mois').fill(`${annee}-12`);
    const [telechargement] = await Promise.all([
      page.waitForEvent('download', { timeout: 60_000 }),
      fenetre.getByRole('button', { name: 'Télécharger' }).click(),
    ]);
    expect(telechargement.suggestedFilename()).toMatch(/^fiche-individuelle-.*\.xlsx$/);
    await verifierPageSaine(page, s);
  });
});
