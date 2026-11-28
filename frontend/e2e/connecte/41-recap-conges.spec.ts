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

/** Le compte QA (super-admin) voit toutes les sociétés : on fixe LEWIS. */
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
 * Lot L21 (demande du 27/11) : « Congés & absences », onglet Récapitulatif.
 * Une ligne par salarié sur la période (par défaut le mois de paie), d'où
 * vient chaque colonne, et l'export Excel. Le test ne fait que des lectures ;
 * côté serveur, le récapitulatif se calcule dans un bloc qui refuse toute
 * écriture (aucun droit à congés d'ancienneté n'est enregistré au passage).
 */
test.describe('Récapitulatif des congés', () => {
  test('montre la société sur le mois de paie et télécharge l’Excel', async ({ page }) => {
    test.setTimeout(120_000);
    const s = surveiller(page);
    await choisirLewis(page);
    await page.goto('/leaves');
    await page.getByTestId('onglet-recap-conges').click({ timeout: 45_000 });

    const recap = page.getByTestId('recap-conges');
    await expect(recap).toBeVisible();
    // Par défaut : du 1er au dernier jour du mois de paie écrit dans l'adresse.
    await expect(page).toHaveURL(/month=\d{4}-\d{2}/);
    const mois = new URL(page.url()).searchParams.get('month')!;
    await expect(recap.locator('#recap-debut')).toHaveValue(`${mois}-01`);
    await expect(recap.locator('#recap-fin')).toHaveValue(new RegExp(`^${mois}-(28|29|30|31)$`));

    // Chargé : le tableau et ses sources, ou « aucun congé » dit en clair.
    await expect(recap.getByText('Chargement du récapitulatif…')).toHaveCount(0, { timeout: 60_000 });
    await expect(recap.getByRole('alert')).toHaveCount(0);
    await expect(recap.getByRole('columnheader', { name: 'Solde CP N-1' })).toBeVisible();
    await expect(recap.getByTestId('recap-sources')).toContainText('D’où viennent les chiffres');

    // Une période à l'envers est refusée avant l'envoi, et l'écran dit pourquoi.
    await recap.locator('#recap-debut').fill(`${mois}-20`);
    await recap.locator('#recap-fin').fill(`${mois}-10`);
    await expect(recap.getByText('Le premier jour est après le dernier.')).toBeVisible();
    await expect(recap.getByRole('button', { name: 'Afficher', exact: true })).toBeDisabled();
    await expect(recap.getByRole('button', { name: 'Exporter (Excel)' })).toBeDisabled();

    // Une période acceptée ne part qu'au clic sur « Afficher ».
    let demandes = 0;
    page.on('request', (r) => {
      if (r.url().includes('/api/absences/recap-societe?')) demandes += 1;
    });
    await recap.locator('#recap-debut').fill(`${mois}-01`);
    await recap.locator('#recap-fin').fill(`${mois}-15`);
    await expect(recap.getByTestId('recap-saisie-en-attente')).toBeVisible();
    expect(demandes).toBe(0);
    await recap.getByRole('button', { name: 'Afficher', exact: true }).click();
    await expect(recap.getByTestId('recap-saisie-en-attente')).toHaveCount(0);
    await expect.poll(() => demandes).toBe(1);
    await expect(recap.getByText('Chargement du récapitulatif…')).toHaveCount(0, { timeout: 60_000 });

    await recap.getByRole('button', { name: 'Mois de paie' }).click();
    await expect(recap.locator('#recap-debut')).toHaveValue(`${mois}-01`);
    const [telechargement] = await Promise.all([
      page.waitForEvent('download', { timeout: 60_000 }),
      recap.getByRole('button', { name: 'Exporter (Excel)' }).click(),
    ]);
    expect(telechargement.suggestedFilename()).toMatch(/^recap-conges-\d{4}-\d{2}-01-\d{4}-\d{2}-\d{2}\.xlsx$/);
    await verifierPageSaine(page, s);
  });
});
