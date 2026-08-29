import { test, expect } from '@playwright/test';
import { API_URL } from '../helpers/env';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

test.describe('Disponibilité de l’environnement de test', () => {
  test('le backend répond sur /health', async ({ request }) => {
    const rep = await request.get(`${API_URL}/health`);
    expect(rep.status()).toBe(200);
  });

  test('le frontend sert l’application', async ({ page }) => {
    const s = surveiller(page);
    await page.goto('/login');
    // Le bandeau orange « ENVIRONNEMENT DE TEST » a été retiré : la resynchro
    // reste sur GET/POST /api/test-env/* et le workflow GitHub.
    await expect(page.getByRole('heading', { name: /connexion/i })).toBeVisible();
    await verifierPageSaine(page, s);
  });
});
