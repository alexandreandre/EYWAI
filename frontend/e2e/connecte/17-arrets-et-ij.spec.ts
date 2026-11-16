import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

/**
 * Retour d'Elsa du 16/11 : les arrêts vivent dans « Arrêts & IJ » (étape 3),
 * plus dans Congés & absences. Lecture seule : aucun arrêt n'est enregistré
 * (la fenêtre est ouverte puis refermée).
 */
test.describe('Arrêts & IJ', () => {
  test('les arrêts se saisissent à l’étape 3, avec la subrogation', async ({ page }) => {
    const s = surveiller(page);

    await page.goto('/leaves');
    await expect(page.getByTestId('renvoi-arrets')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole('button', { name: /Enregistrer un arrêt/ })).toHaveCount(0);

    await page.getByTestId('renvoi-arrets').getByRole('link', { name: 'Arrêts & IJ' }).click();
    await expect(page.getByRole('heading', { name: 'Arrêts & IJ' })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/^Arrêts de /)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('Rapprochement détaillé (facultatif)')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sync Net-Entreprises' })).toHaveCount(0);

    await page.getByRole('button', { name: /Enregistrer un arrêt/ }).click();
    const fenetre = page.getByRole('dialog');
    await expect(fenetre.getByText('Subrogation', { exact: true })).toBeVisible({ timeout: 30_000 });
    await expect(fenetre.getByText(/Règle de la société/)).toBeVisible();
    await fenetre.getByRole('button', { name: 'Annuler' }).click();
    await expect(fenetre).toBeHidden();

    await verifierPageSaine(page, s);
  });
});
