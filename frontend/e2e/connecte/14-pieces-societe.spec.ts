import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

/** Rien n'est écrit : le dépôt est intercepté avant de quitter le navigateur. */
test.describe('Pièces de la société', () => {
  test('l’encart dit ce qui manque et le dépôt part vers Martine', async ({ page }) => {
    const s = surveiller(page);
    let depots = 0;
    await page.route('**/api/company/pieces', async (route) => {
      if (route.request().method() !== 'POST') return route.fallback();
      depots += 1;
      await route.fulfill({ status: 201, json: { depose: true } });
    });

    await page.goto('/company');
    const encart = page.getByText('Pièces de la société').locator('xpath=ancestor::div[contains(@class,"rounded")][1]');
    await expect(encart).toBeVisible({ timeout: 30_000 });
    await expect(encart.getByText('Contrat de mutuelle')).toBeVisible({ timeout: 30_000 });

    await page.getByLabel('Fichier pour Contrat de mutuelle').setInputFiles({
      name: 'contrat.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4'),
    });
    await expect.poll(() => depots).toBe(1);
    await expect(page.getByText('Pièce déposée').first()).toBeVisible();

    await verifierPageSaine(page, s);
  });
});
