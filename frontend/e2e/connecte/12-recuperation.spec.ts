import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

// Heures de récupération (05/11/2026) : le réglage de la société, la carte du
// bulletin et ses gestes. Rien n'est écrit : le bulletin relu reçoit un compteur
// simulé, les réglages et les gestes sont interceptés et comptés.

async function entetes(page: Page) {
  const { jeton, societe } = await page.evaluate(() => ({
    jeton: localStorage.getItem('authToken'),
    societe: localStorage.getItem('activeCompanyId'),
  }));
  return { Authorization: `Bearer ${jeton}`, ...(societe ? { 'X-Active-Company': societe } : {}) };
}

test('compteur de récupération : réglage, bulletin, choix du mois', async ({ page }) => {
  test.setTimeout(240_000);
  // Le script tourne aussi dans l'iframe sans origine de l'aperçu, où localStorage lève.
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  await page.route('**/api/client-errors', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    await route.fulfill({ status: 204, body: '' });
  });
  const s = surveiller(page);

  // --- Le réglage de la société
  const reglagesEcrits: unknown[] = [];
  await page.route('**/api/modulation/settings', async (route) => {
    const req = route.request();
    if (req.method() === 'PATCH') {
      const corps = req.postDataJSON();
      reglagesEcrits.push(corps);
      const reponse = await page.request.get(req.url(), { headers: await entetes(page) });
      const actuels = await reponse.json();
      await route.fulfill({ json: { ...actuels, ...corps } });
      return;
    }
    return route.fallback();
  });
  await page.goto('/company');
  await expect(page.getByText(/société|entreprise/i).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole('tab', { name: /paie/i }).first().click();
  await page.getByRole('button', { name: /^temps de travail/i }).first().click();
  await page.getByRole('button', { name: /organisation du temps & compte d'heures/i }).first().click();
  const carte = page.getByTestId('reglage-heures-sup');
  await expect(carte).toBeVisible({ timeout: 20_000 });
  await carte.getByLabel(/mises au compteur de récupération/i).click();
  await expect(carte.getByText(/L3121-37/)).toBeVisible();
  await carte.getByLabel(/plafond du compteur/i).fill('abc');
  await expect(carte.getByRole('button', { name: /enregistrer/i })).toBeDisabled();
  await carte.getByLabel(/plafond du compteur/i).fill('40');
  await carte.getByRole('button', { name: /enregistrer/i }).click();
  await expect.poll(() => reglagesEcrits.length).toBe(1);
  expect(reglagesEcrits[0]).toMatchObject({
    hour_account_enabled: true,
    hs_routing_policy: 'account_all',
    max_account_balance_hours: 40,
  });

  // --- Un vrai bulletin, relu avec un compteur simulé
  const bulletins = await page.request.get(`${API_URL}/api/employees/summary?status=payroll`, {
    headers: await entetes(page),
  });
  const salaries = (await bulletins.json()) as { id: string }[];
  let idBulletin: string | null = null;
  for (const salarie of salaries.slice(0, 40)) {
    const r = await page.request.get(`${API_URL}/api/employees/${salarie.id}/payslips`, {
      headers: await entetes(page),
      failOnStatusCode: false,
    });
    if (!r.ok()) continue;
    const lignes = (await r.json()) as { id: string; origine?: string }[];
    const calcule = lignes.find((l) => l.origine !== 'importe');
    if (calcule) {
      idBulletin = calcule.id;
      break;
    }
  }
  expect(idBulletin, 'un bulletin calculé à relire').toBeTruthy();

  let etat: 'compteur' | 'paye' = 'compteur';
  const gestes: { url: string; corps: unknown }[] = [];
  let recalculs = 0;
  await page.route(new RegExp(`/api/payslips/${idBulletin}(/details?)?(\\?.*)?$`), async (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    const reponse = await route.fetch();
    const detail = await reponse.json();
    const paye = etat === 'paye';
    await route.fulfill({
      response: reponse,
      json: {
        ...detail,
        status: 'brouillon',
        manually_edited: false,
        manual_edit_locked: false,
        period_edit_locked: false,
        payslip_data: {
          ...detail.payslip_data,
          modulation_account: {
            hs_realisees: 4,
            hs_credited: paye ? 0 : 4,
            hs_paid: paye ? 4 : 0,
            repos_credite: paye ? 0 : 5,
            paye_ce_mois: paye,
            au_compteur_ce_mois: false,
            regle: 'account_all',
          },
          pied_de_page: {
            ...detail.payslip_data?.pied_de_page,
            solde_conges: {
              ...detail.payslip_data?.pied_de_page?.solde_conges,
              recuperation: { acquis: 5, pris: 0, paye: 0, solde: 7, payable: 2, prises: [] },
            },
          },
        },
      },
    });
  });
  await page.route('**/api/modulation/recuperation/**', async (route) => {
    gestes.push({ url: route.request().url(), corps: route.request().postDataJSON() });
    await route.fulfill({ json: { status: 'ok' } });
  });
  // L'aperçu ne fait que rendre le bulletin (POST sans écriture) : simulé, la garde reste stricte.
  await page.route(`**/api/payslips/${idBulletin}/preview`, async (route) => {
    await route.fulfill({ json: { html: '<p>Aperçu QA</p>' } });
  });
  await page.route('**/api/actions/generate-payslip', async (route) => {
    recalculs += 1;
    etat = 'paye';
    await route.fulfill({ json: { status: 'success', warnings: [] } });
  });

  await page.goto(`/payslips/${idBulletin}/edit`);
  const recup = page.getByTestId('carte-recuperation');
  await expect(recup).toBeVisible({ timeout: 40_000 });
  await expect(recup.getByText(/4 h d’heures sup mises au compteur ce mois-ci, soit 5 h de repos/)).toBeVisible();
  await expect(recup.getByText(/exonération d'impôt/)).toBeVisible();
  await expect(recup.getByRole('button', { name: /payer le solde \(2 h\)/i })).toBeVisible();

  // « Payer ces heures ce mois-ci » : le choix part, le bulletin se recalcule.
  await recup.getByRole('button', { name: /payer ces heures ce mois-ci/i }).click();
  await expect.poll(() => gestes.length).toBe(1);
  expect(gestes[0].corps).toEqual({ choix: 'payer', heures_sup: 4 });
  await expect.poll(() => recalculs).toBe(1);
  await expect(recup.getByRole('button', { name: /remettre au compteur/i })).toBeVisible({ timeout: 20_000 });

  await verifierPageSaine(page, s);
});
