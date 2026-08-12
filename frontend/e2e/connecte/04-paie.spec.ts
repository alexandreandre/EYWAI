import { test, expect } from '@playwright/test';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

test.describe('Parcours paie (lecture seule)', () => {
  test('la page paie s’affiche et ses onglets répondent', async ({ page }) => {
    const s = surveiller(page);
    await page.goto('/payroll');
    // Premier rendu parfois lent à froid (Cloud Run + données) : 30 s.
    await expect(page.getByText(/gestion de la paie/i).first()).toBeVisible({ timeout: 30_000 });

    // Parcourt les onglets présents (vue par salarié / par mois).
    const onglets = page.getByRole('tab');
    const n = await onglets.count();
    for (let i = 0; i < n; i++) {
      await onglets.nth(i).click();
    }

    await verifierPageSaine(page, s);
  });

  test('la page de génération liste les salariés éligibles sans erreur', async ({ page }) => {
    const s = surveiller(page);
    await page.goto('/payroll/generate');
    await expect(page).not.toHaveURL(/\/login/);
    // Lecture seule : on ne clique JAMAIS sur le bouton de génération ici.
    await verifierPageSaine(page, s);
  });
});
