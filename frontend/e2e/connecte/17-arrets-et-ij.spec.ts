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
    // « Pas d'import, pas d'export » (Elsa, 16/11) : le rapprochement par fichiers est retiré.
    await expect(page.getByText(/Rapprochement détaillé/)).toHaveCount(0);
    await expect(page.getByRole('button', { name: /Import décompte|Import virements|Export audit/ })).toHaveCount(0);
    await expect(page.getByText(/cliquez sur « Reçues »/)).toBeVisible();

    await page.getByRole('button', { name: /Enregistrer un arrêt/ }).click();
    const fenetre = page.getByRole('dialog');
    await expect(fenetre.getByText('Subrogation', { exact: true })).toBeVisible({ timeout: 30_000 });
    await expect(fenetre.getByText(/Règle de la société/)).toBeVisible();
    await fenetre.getByRole('button', { name: 'Annuler' }).click();
    await expect(fenetre).toBeHidden();

    await verifierPageSaine(page, s);
  });

  test('un type d’arrêt vidé ne reste pas affiché (retour du 26/11)', async ({ page }) => {
    // Nature changée puis remise : le type « Maladie simple » restait affiché
    // alors qu'il était vidé, et l'enregistrement était refusé. Aucune écriture.
    const ecritures: string[] = [];
    await page.route('**/api/**', async (route) => {
      const req = route.request();
      if (req.method() === 'GET' || req.url().includes('/api/auth/') || req.url().includes('/api/client-errors')) {
        return route.fallback();
      }
      ecritures.push(`${req.method()} ${req.url()}`);
      await route.abort();
    });
    await page.goto('/leaves');
    await page.getByTestId('renvoi-arrets').getByRole('link', { name: 'Arrêts & IJ' }).click();
    await page.getByRole('button', { name: /Enregistrer un arrêt/ }).click();
    const fenetre = page.getByRole('dialog');
    await fenetre.locator('#arret-type').click();
    await page.getByRole('option', { name: /Maladie simple/ }).click();
    await expect(fenetre.locator('#arret-type')).toContainText('Maladie simple');
    await fenetre.locator('#absence-type').click();
    await page.getByRole('option', { name: /Congé maternité/ }).click();
    await fenetre.locator('#absence-type').click();
    await page.getByRole('option', { name: /Arrêt maladie/ }).click();
    await expect(fenetre.locator('#arret-type')).toContainText(/Sélectionner le type d.arrêt/);
    await fenetre.getByRole('button', { name: 'Annuler' }).click();
    expect(ecritures).toEqual([]);
  });
});
