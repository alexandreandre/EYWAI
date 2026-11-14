import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

/**
 * Retours d'Elsa du 13/11 : paliers de médaille libres (10, 20, 30, 40 ans) et
 * réglage « maintien seulement quand le salarié a transmis ses IJ ».
 * Rien n'est écrit : l'enregistrement est intercepté avant de quitter le navigateur.
 */
test.describe('Médailles et maintien', () => {
  test('on ajoute un palier de 10 ans et le réglage des IJ est à l’écran', async ({ page }) => {
    const s = surveiller(page);
    let envoye: { tiers?: { years: number }[] } | null = null;
    await page.route('**/api/work-medal-settings/', async (route) => {
      if (route.request().method() !== 'PUT') return route.fallback();
      envoye = route.request().postDataJSON();
      await route.fulfill({ status: 200, json: { company_id: 'simule', ...envoye } });
    });

    await page.goto('/company');
    await page.getByRole('tab', { name: /Paramètres paie|Paie/ }).click();
    await page.getByRole('button', { name: 'Tout développer' }).click();

    const ajouter = page.getByRole('button', { name: 'Ajouter un palier' });
    await expect(ajouter).toBeVisible({ timeout: 30_000 });
    const avant = await page.getByLabel('Années').count();
    await ajouter.click();
    await expect(page.getByLabel('Années')).toHaveCount(avant + 1);
    const nouveau = page.getByLabel('Années').nth(avant);
    await nouveau.fill('10');
    await expect(page.getByText('Prime d’ancienneté, soumise à cotisations').first()).toBeVisible();

    const carte = page
      .getByText('Barème des primes')
      .locator('xpath=ancestor::div[contains(@class,"rounded")][1]');
    await carte.getByRole('button', { name: 'Enregistrer' }).click();
    await expect.poll(() => envoye?.tiers?.some((t) => t.years === 10) ?? false).toBe(true);

    // Carte « Maintien de salaire », onglet Prévoyance (avec la subrogation).
    await page.getByRole('tab', { name: 'Prévoyance', exact: true }).click();
    const reglageIj = page.getByText('Maintien seulement quand le salarié a transmis ses IJ');
    await reglageIj.scrollIntoViewIfNeeded({ timeout: 30_000 });
    await expect(reglageIj).toBeVisible();
    await expect(page.getByRole('switch', { name: 'Maintien seulement quand le salarié a transmis ses IJ' })).toBeVisible();
    await verifierPageSaine(page, s);
  });
});
