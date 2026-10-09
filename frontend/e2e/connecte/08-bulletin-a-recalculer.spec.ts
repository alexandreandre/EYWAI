import { test, expect, type Page } from '@playwright/test';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

/**
 * Badge « À recalculer » : lectures et génération interceptées, société de
 * démonstration seulement. Aucun calendrier réel n'est modifié.
 */
const SALARIE_ID = '00000000-0000-4000-8000-000000000091';
const BULLETIN_ID = '00000000-0000-4000-8000-000000000092';

function salarieDemo() {
  return {
    id: SALARIE_ID,
    first_name: 'Jeanne',
    last_name: 'Essai',
    job_title: 'Opératrice QA',
    hire_date: '2026-01-05',
    date_debut_execution: '2026-01-05',
    employment_status: 'actif',
    missing_payroll_fields: [],
    payroll_eligible: true,
    profile_complete: true,
  };
}

function ligneBulletin(aRecalculer: boolean | null) {
  return {
    id: BULLETIN_ID,
    name: 'Bulletin_Jeanne_Essai_05-2026.pdf',
    month: 5,
    year: 2026,
    url: 'https://exemple.test/bulletin.pdf',
    preview_url: 'https://exemple.test/bulletin.pdf',
    net_a_payer: aRecalculer ? 1400 : 1480,
    salaire_brut: aRecalculer ? 1800 : 1900,
    heures_sup: aRecalculer ? 2 : 4,
    a_recalculer: aRecalculer,
    origine: 'calcule',
    warnings: [],
    points_a_arbitrer: [],
    manually_edited: false,
    edit_count: 0,
  };
}

async function preparerPaiePerimee(page: Page) {
  let perime = true;
  await page.addInitScript(() => localStorage.removeItem('martine-rq-cache-v2'));
  await page.route('**/api/employees/summary**', async (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    await route.fulfill({ json: [salarieDemo()] });
  });
  await page.route(`**/api/employees/${SALARIE_ID}/payslips**`, async (route) => {
    await route.fulfill({ json: [ligneBulletin(perime ? true : false)] });
  });
  await page.route('**/api/actions/generate-payslip**', async (route) => {
    perime = false;
    await route.fulfill({
      json: {
        status: 'success',
        message: 'Bulletin généré avec succès.',
        download_url: 'https://exemple.test/bulletin.pdf',
        payslip_id: BULLETIN_ID,
        warnings: [],
        salaire_brut: 1900,
        net_a_payer: 1480,
        heures_sup: 4,
      },
    });
  });
}

test('un bulletin périmé se dit À recalculer, puis le badge disparaît', async ({ page }) => {
  const s = surveiller(page);
  await preparerPaiePerimee(page);
  await page.goto('/payroll?view=month&month=2026-05');
  await expect(page.getByText(/gestion de la paie/i).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Jeanne Essai').first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('À recalculer').first()).toBeVisible();
  await expect(page.getByRole('button', { name: /Recalculer tout ce qui a changé/i }).first()).toBeVisible();

  await page.getByRole('button', { name: /^Recalculer$/ }).first().click();
  await expect(page.getByText('Bulletin recalculé').first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('À recalculer')).toHaveCount(0);

  await verifierPageSaine(page, s);
});
