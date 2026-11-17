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

/** Société du compte QA par son nom, rendue active. */
async function choisirSociete(page: Page, nom: RegExp): Promise<string> {
  await page.goto('/');
  const societes = (await (
    await page.request.get(`${API_URL}/api/users/my-companies`, { headers: await entetes(page) })
  ).json()) as { company_id: string; company_name?: string }[];
  const soc = societes.find((c) => nom.test(c.company_name ?? ''));
  expect(soc, `la société ${nom} du compte QA`).toBeTruthy();
  await page.evaluate((id) => {
    localStorage.setItem('activeCompanyId', id);
    localStorage.removeItem('martine-rq-cache-v2');
  }, soc!.company_id);
  return soc!.company_id;
}

/** Premier salarié au forfait heures de la société active. */
async function unSalarieEnHeures(page: Page): Promise<string> {
  const liste = (await (
    await page.request.get(`${API_URL}/api/employees/summary`, { headers: await entetes(page) })
  ).json()) as { id: string; is_forfait_jour?: boolean }[];
  const s = liste.find((x) => !x.is_forfait_jour);
  expect(s, 'un salarié en heures').toBeTruthy();
  return s!.id;
}

test('panier tapé à la main dans Primes : part non soumis, avec le nombre', async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  // L'enregistrement est simulé : le corps est relevé, rien ne part.
  const corps: Record<string, unknown>[] = [];
  await page.route('**/api/monthly-inputs', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    corps.push(...(JSON.parse(route.request().postData() ?? '[]') as Record<string, unknown>[]));
    await route.fulfill({ json: { status: 'ok', inserted: 1 } });
  });
  const s = surveiller(page);
  await choisirSociete(page, /mont[\s-]?blanc/i);

  await page.goto('/saisies');
  const nouvelle = page.getByRole('button', { name: /Nouvelle saisie/ }).first();
  await expect(nouvelle).toBeVisible({ timeout: 45_000 });
  await nouvelle.click();
  const fen = page.getByRole('dialog');
  await fen.getByPlaceholder('Sélectionnez ou saisissez un nom...').fill('Panier repas');
  await fen.getByRole('heading', { name: /Ajouter une saisie du mois/ }).click();
  await expect(fen.getByTestId('nombre-paniers')).toBeVisible();
  await expect(fen.locator('#is_socially_taxed')).not.toBeChecked();
  await expect(fen.locator('#is_taxable')).not.toBeChecked();

  // Coché « soumise » : le bloc disparaît, une ligne dit que le panier est cotisé.
  await fen.locator('#is_socially_taxed').click();
  await expect(fen.getByTestId('nombre-paniers')).toHaveCount(0);
  await expect(fen.getByTestId('panier-soumis')).toBeVisible();
  await fen.locator('#is_socially_taxed').click();
  await expect(fen.getByTestId('nombre-paniers')).toBeVisible();

  await fen.getByText(/^Montant \(€\)/).locator('xpath=..').locator('input').first().fill('150');
  await fen.locator('#nombre_paniers').fill('20');
  const choix = fen.getByRole('combobox').filter({ hasText: /Sélectionner des employés/ });
  await choix.scrollIntoViewIfNeeded();
  await choix.click();
  await page.locator('[cmdk-item]').nth(1).click();
  await fen.getByRole('heading', { name: /Ajouter une saisie du mois/ }).click();
  await fen.getByRole('button', { name: 'Enregistrer' }).click();

  await expect.poll(() => corps.length, { timeout: 15_000 }).toBeGreaterThan(0);
  expect(corps[0]).toMatchObject({
    name: 'Panier repas',
    is_socially_taxed: false,
    is_taxable: false,
    payroll_quantity: 20,
    situation_repas: 'sur_lieu_travail',
  });
  await verifierPageSaine(page, s);
});

test('activité partielle au calendrier : choix chez LEWIS, absent ailleurs', async ({ page }) => {
  test.setTimeout(150_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);

  const menuDuJour = async () => {
    await expect(page.getByRole('button', { name: /Importer un relevé/ })).toBeVisible({ timeout: 45_000 });
    await page.locator('button', { hasText: /^Travail$/ }).nth(3).click();
    return page.locator('[data-radix-popper-content-wrapper]').last();
  };

  // Une société sans activité partielle : le choix n'existe pas (d'abord, rien n'est modifié à l'écran).
  await choisirSociete(page, /mont[\s-]?blanc/i);
  await page.goto(`/employees/${await unSalarieEnHeures(page)}?tab=calendrier`);
  const autre = await menuDuJour();
  await expect(autre.getByText(/^Repos$/).first()).toBeVisible();
  await expect(autre.getByText(/^Activité partielle$/)).toHaveCount(0);
  await page.keyboard.press('Escape');

  // LEWIS : le choix est là, et la fiche tient une fois le jour passé en activité partielle.
  await choisirSociete(page, /^lewis/i);
  await page.goto(`/employees/${await unSalarieEnHeures(page)}?tab=calendrier`);
  const menu = await menuDuJour();
  await menu.getByText(/^Activité partielle$/).first().click();
  await expect(page.locator('button', { hasText: /^Activité partielle$/ }).first()).toBeVisible();
  await expect(page.getByText("Cette page n'a pas pu s'afficher")).toHaveCount(0);
  // Rouvrir le menu du jour déjà en activité partielle (le plantage du 17/11).
  await page.locator('button', { hasText: /^Activité partielle$/ }).first().click();
  await expect(page.locator('[data-radix-popper-content-wrapper]').last().getByText(/^Activité partielle$/).first()).toBeVisible();
  await expect(page.getByText("Cette page n'a pas pu s'afficher")).toHaveCount(0);
  await page.keyboard.press('Escape');
  await verifierPageSaine(page, s);
});
