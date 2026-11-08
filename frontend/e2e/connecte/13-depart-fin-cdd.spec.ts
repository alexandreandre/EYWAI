import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

// « Fin de CDD » proposée d'office dans le formulaire de départ (05/11/2026).
// Rien n'est écrit : la liste des salariés et l'aperçu du préavis sont simulés,
// le formulaire n'est jamais envoyé (garde anti-écriture).
// Un seul parcours, sur une seule page (voir 08-mode-paie).

const CDD = '00000000-0000-4000-8000-0000000000c1';
const CDI = '00000000-0000-4000-8000-0000000000c2';

test.use({ storageState: { cookies: [], origins: [] } });

async function seConnecter(page: Page) {
  await page.goto('/login');
  await page.locator('#login-username').fill(process.env.E2E_QA_EMAIL!);
  await page.locator('#login-password').fill(process.env.E2E_QA_PASSWORD!);
  await page.getByRole('button', { name: /se connecter/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 30_000 });
}

test('un CDD à terme : Fin de CDD et sa date proposées, un choix de la RH jamais remplacé', async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => localStorage.removeItem('martine-rq-cache-v2'));
  await seConnecter(page);
  const s = surveiller(page);

  await page.route('**/api/employee-exits/eligible-employees', async (route) => {
    await route.fulfill({
      json: [
        { id: CDD, first_name: 'Essai', last_name: 'Cedede', contract_type: 'CDD', contract_end_date: '2026-09-30' },
        { id: CDI, first_name: 'Essai', last_name: 'Cedei', contract_type: 'CDI', contract_end_date: null },
      ],
    });
  });
  await page.route('**/api/employee-exits/notice-period-preview**', async (route) => {
    await route.fulfill({
      json: {
        employee_id: CDD,
        exit_type: 'fin_cdd',
        reference_date: '2026-09-01',
        notice_period_days: 0,
        source: 'not_applicable',
        label: 'Aucun préavis',
        detail: '',
        warnings: [],
        applicable: false,
        has_collective_agreement: false,
      },
    });
  });

  await page.goto('/employee-exits');
  await page.getByRole('button', { name: /nouveau départ/i }).first().click();
  const fenetre = page.getByRole('dialog');
  const motif = fenetre.locator('#exit_type');
  const dernierJour = fenetre.locator('#last_working_day');
  const phrase = fenetre.getByTestId('motif-propose-info');
  const choisirSalarie = async (nom: RegExp) => {
    await fenetre.locator('#employee').click();
    await page.getByRole('option', { name: nom }).click();
  };

  await expect(motif).toContainText('Démission');

  // Un CDD à terme : motif, date et phrase.
  await choisirSalarie(/Cedede/);
  await expect(motif).toContainText('Fin de CDD');
  await expect(dernierJour).toHaveValue('2026-09-30');
  await expect(phrase).toHaveText('Proposé par Martine : CDD qui finit le 30/09/2026.');

  // Un CDI ensuite : la proposition s'efface.
  await choisirSalarie(/Cedei/);
  await expect(motif).toContainText('Démission');
  await expect(dernierJour).toHaveValue('');
  await expect(phrase).toHaveCount(0);

  // De nouveau le CDD, puis la RH choisit un autre motif : il n'est plus remplacé.
  await choisirSalarie(/Cedede/);
  await expect(motif).toContainText('Fin de CDD');
  await motif.click();
  await page.getByRole('option', { name: /Fin de période d'essai/ }).click();
  await expect(phrase).toHaveCount(0);
  await choisirSalarie(/Cedei/);
  await expect(motif).toContainText("Fin de période d'essai");

  await verifierPageSaine(page, s);
});
