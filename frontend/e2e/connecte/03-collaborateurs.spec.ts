import { test, expect } from '@playwright/test';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

test.describe('Parcours collaborateurs', () => {
  test('la liste s’affiche et une fiche salarié s’ouvre', async ({ page }) => {
    const s = surveiller(page);
    await page.goto('/employees');
    // Premier rendu parfois lent à froid (Cloud Run + données) : 30 s.
    await expect(page.getByText(/gestion des collaborateurs/i).first()).toBeVisible({ timeout: 30_000 });

    // Ouvre la première fiche disponible ; un état vide est toléré mais signalé.
    const lienFiche = page.locator('a[href^="/employees/"]').first();
    if ((await lienFiche.count()) === 0) {
      test.info().annotations.push({
        type: 'avertissement',
        description: 'Aucun salarié listé — fiche non testée (état vide ou société active sans effectif).',
      });
    } else {
      await lienFiche.click();
      await page.waitForURL(/\/employees\/[^/]+$/, { timeout: 30_000 });
      await expect(page.locator('#root > *:visible').first()).toBeVisible();
    }

    await verifierPageSaine(page, s);
  });
});
