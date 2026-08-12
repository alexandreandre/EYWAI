import { test, expect } from '@playwright/test';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

test.describe('Exports (paie, DSN, paiements)', () => {
  test('chaque onglet de la page Exports se rend sans erreur', async ({ page }) => {
    const s = surveiller(page);
    await page.goto('/exports');
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.locator('#root > *:visible').first()).toBeVisible();

    const onglets = page.getByRole('tab');
    const n = await onglets.count();
    test.info().annotations.push({ type: 'info', description: `${n} onglets détectés` });
    for (let i = 0; i < n; i++) {
      await onglets.nth(i).click();
      // Consultation uniquement : aucun bouton d'export/dépôt n'est cliqué.
    }

    await verifierPageSaine(page, s);
  });
});
