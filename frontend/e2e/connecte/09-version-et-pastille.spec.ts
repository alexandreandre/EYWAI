import { test, expect } from '../helpers/garde';

/**
 * Ce que la gestionnaire voit en permanence sur le site de paie : la version en
 * bas du menu (à donner au support pour savoir quel code a calculé un bulletin)
 * et la pastille qui dit que les données sont réelles. Lecture seule.
 */
test('la version du site s’affiche en bas du menu', async ({ page }, testInfo) => {
  await page.goto('/');
  const version = page.getByText(/^Version paie-\d{4}-\d{2}-\d{2}\.\d+ · [0-9a-f]{7}$/);
  await expect(version).toBeVisible({ timeout: 30_000 });
  await expect(version).toHaveAttribute('title', /^paie-\d{4}-\d{2}-\d{2}\.\d+ \(commit [0-9a-f]{40}\)$/);
  await page.screenshot({ path: testInfo.outputPath('menu.png') });
});

test('la pastille dit que les données sont réelles', async ({ page }, testInfo) => {
  await page.goto('/');
  const pastille = page.getByRole('status').filter({ hasText: 'Données réelles · envois limités' });
  await expect(pastille).toBeVisible({ timeout: 30_000 });
  await expect(pastille).toHaveAttribute('title', /réelles et conservées/);
  await expect(page.getByText('Environnement de test', { exact: true })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('pastille.png') });
});
