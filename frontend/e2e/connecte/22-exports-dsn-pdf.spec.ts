import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

/**
 * Page Notion d'Elsa du 17/11 : onglet « DSN » des exports, ouvert par défaut,
 * avec la déclaration, les charges par caisse, l'OD globale et le journal ;
 * OD charges, OD PAS, OD salaires, FEC, Sage, Quadra et générique retirés ;
 * chaque export en tableau propose le PDF. Rien n'est généré (consultation seulement).
 */
test('exports : onglet DSN par défaut, exports retirés, choix du PDF', async ({ page }) => {
  test.setTimeout(120_000);
  const s = surveiller(page);
  await page.goto('/exports');
  await expect(page.getByRole('tab', { name: 'DSN' })).toHaveAttribute('data-state', 'active', { timeout: 30_000 });

  const panneau = page.getByRole('tabpanel');
  for (const carte of ['Déclaration mensuelle', 'Charges sociales par caisse', 'OD globale de paie', 'Journal de paie']) {
    await expect(panneau.getByText(carte, { exact: true })).toBeVisible();
  }

  // Le journal propose le PDF d'office, à côté d'Excel et du CSV.
  await panneau
    .getByText('Journal de paie', { exact: true })
    .locator('xpath=ancestor::div[contains(@class,"rounded")][1]')
    .getByRole('button', { name: 'Configurer' })
    .click();
  const fenetre = page.getByRole('dialog');
  await fenetre.getByLabel(/Format de fichier/).click();
  await expect(page.getByRole('option', { name: 'PDF (.pdf)' })).toBeVisible();
  await page.keyboard.press('Escape');
  await page.keyboard.press('Escape');

  // Paie & Comptabilité : plus d'OD salaires, OD charges, OD PAS, FEC ni Sage ;
  // plus de cartes Quadra ni générique, en double de l'OD globale (Elsa, 20/11).
  await page.getByRole('tab', { name: /Paie & Comptabilité|^Paie$/ }).click();
  const paie = page.getByRole('tabpanel');
  await expect(paie.getByText('Acomptes & avances', { exact: true })).toBeVisible({ timeout: 15_000 });
  for (const retire of [
    'OD Salaires',
    'OD Charges sociales',
    'OD PAS',
    'FEC',
    'Export format Sage',
    'Export format Quadra',
    'Export format comptable générique',
  ]) {
    await expect(paie.getByText(retire, { exact: true })).toHaveCount(0);
  }

  await verifierPageSaine(page, s);
});
