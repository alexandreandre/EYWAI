import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

/**
 * Lot L18 (27/11) : « Fiche individuelle (Excel) » sur la fiche collaborateur,
 * les cumuls mois par mois lus sur les bulletins (utile pour l'indemnité de
 * départ). Lecture seule : le fichier est téléchargé, rien n'est enregistré.
 */
test.describe('Fiche individuelle', () => {
  test('le bouton télécharge la fiche Excel de l’année civile', async ({ page }) => {
    test.setTimeout(120_000);
    const s = surveiller(page);
    await page.goto('/employees');
    const lienFiche = page.locator('a[href^="/employees/"]').first();
    await expect(lienFiche).toBeVisible({ timeout: 45_000 });
    await lienFiche.click();
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
