import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

/**
 * Lot L18 (27/11) : la prévoyance quitte l'onglet « Paramètres paie » pour
 * l'onglet « Mutuelle et prévoyance », à côté de la mutuelle.
 * Lecture seule : rien n'est enregistré.
 */
test.describe('Mutuelle et prévoyance', () => {
  test('les formules de prévoyance sont dans l’onglet « Mutuelle et prévoyance »', async ({ page }) => {
    const s = surveiller(page);
    await page.goto('/company');

    const onglet = page.getByRole('tab', { name: /Mutuelle et prévoyance/ });
    await expect(onglet).toBeVisible({ timeout: 30_000 });
    await onglet.click();
    await expect(page.getByText('Mutuelle & complémentaire santé').first()).toBeVisible({ timeout: 30_000 });
    const carte = page.locator('#prevoyance');
    await expect(carte.getByText('Prévoyance', { exact: true })).toBeVisible();
    await expect(carte.getByText(/Créez ici les formules de prévoyance de la société/)).toBeVisible();

    // L'onglet « Paramètres paie » n'a plus de section Prévoyance.
    await page.getByRole('tab', { name: /Paramètres paie|Paie/ }).click();
    await page.getByRole('button', { name: 'Tout développer' }).click();
    await expect(page.getByText('Formules de la société, à choisir sur la fiche du salarié')).toHaveCount(0);

    // Un ancien lien « ?tab=prevoyance » ouvre le bon onglet.
    await page.goto('/company?tab=prevoyance');
    await expect(page.locator('#prevoyance')).toBeVisible({ timeout: 30_000 });
    await verifierPageSaine(page, s);
  });
});
