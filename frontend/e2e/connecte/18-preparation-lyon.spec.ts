import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * Retours d'Elsa du 16/11 (préparation de Lyon) : réglage « les N premières
 * heures au compteur », onglet « Compteur récup », réglage de l'activité
 * partielle. Lecture seule : aucune écriture ne part (toute requête qui
 * écrit est refusée et comptée).
 */
async function entetes(page: Page) {
  const { jeton, societe } = await page.evaluate(() => ({
    jeton: localStorage.getItem('authToken'),
    societe: localStorage.getItem('activeCompanyId'),
  }));
  return { Authorization: `Bearer ${jeton}`, ...(societe ? { 'X-Active-Company': societe } : {}) };
}

test('préparation de Lyon : heures sup, compteur récup, activité partielle', async ({ page }) => {
  test.setTimeout(180_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const ecritures: string[] = [];
  await page.route('**/api/**', async (route) => {
    const req = route.request();
    const methode = req.method();
    if (methode === 'GET' || req.url().includes('/api/auth/') || req.url().includes('/api/client-errors')) {
      return route.fallback();
    }
    ecritures.push(`${methode} ${req.url()}`);
    await route.abort();
  });
  const s = surveiller(page);

  await page.goto('/');
  const societes = (await (
    await page.request.get(`${API_URL}/api/users/my-companies`, { headers: await entetes(page) })
  ).json()) as { company_id: string; company_name?: string }[];
  const maji = societes.find((c) => /^maji$/i.test(c.company_name ?? ''));
  expect(maji, 'la société MAJI du compte QA').toBeTruthy();
  await page.evaluate((id) => localStorage.setItem('activeCompanyId', id), maji!.company_id);

  // Réglage des heures sup : trois choix, N premières heures (14 par défaut).
  await page.goto('/company');
  await expect(page.getByText(/société|entreprise/i).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole('tab', { name: /paie/i }).first().click();
  await page.getByRole('button', { name: /^temps de travail/i }).first().click();
  await page.getByRole('button', { name: /organisation du temps & compte d'heures/i }).first().click();
  const carte = page.getByTestId('reglage-heures-sup');
  await expect(carte).toBeVisible({ timeout: 20_000 });
  await expect(carte.getByLabel(/payées au bulletin/i)).toBeVisible();
  await expect(carte.getByLabel(/toutes au compteur de récupération/i)).toBeVisible();
  await carte.getByLabel(/premières heures du mois au compteur/i).click();
  await expect(carte.getByTestId('hs-premieres-heures')).toHaveValue(/^\d+([.,]\d+)?$/);
  await carte.getByTestId('hs-premieres-heures').fill('abc');
  await expect(carte.getByRole('button', { name: /enregistrer/i })).toBeDisabled();

  // Réglage de l'activité partielle.
  const ap = page.getByTestId('reglage-activite-partielle');
  await expect(ap).toBeVisible({ timeout: 20_000 });
  await expect(ap.getByText(/Activité partielle en cours dans cette société/)).toBeVisible();

  // Temps de travail : l'onglet s'appelle « Compteur récup ».
  await page.goto('/suivi-temps-travail');
  await expect(page.getByRole('tab', { name: 'Compteur récup' })).toBeVisible({ timeout: 30_000 });
  await page.getByRole('tab', { name: 'Compteur récup' }).click();
  await expect(page.getByText(/1 h 15 au compteur/)).toBeVisible({ timeout: 20_000 });

  expect(ecritures, 'aucune écriture').toEqual([]);
  await verifierPageSaine(page, s);
});
