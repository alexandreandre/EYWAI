import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

/**
 * Retour d'Elsa (26/11) sur l'import des pointages MBC : le bandeau
 * « Relevé à relire — Martine a retenu les heures du badge, pas les
 * annotations : lun 21/09 « CP », … » était coupé et illisible. Il se lit
 * maintenant jour par jour, par salarié, et se déplie en entier.
 * Lecture seule : l'analyse du relevé est simulée, rien n'est enregistré.
 */
const ANNOTATIONS =
  'Relevé à relire — Martine a retenu les heures du badge, pas les annotations : ' +
  'lun 21/09 « CP » ; mar 22/09 « ?????? absent 7,5 » ; mer 23/09 « PANIERS 3 » ; ' +
  'jeu 24/09 « RTT » ; ven 25/09 « +1 », badgeage incomplet, 3,53 h lues.';

const PROPOSITION = {
  year: 2026,
  month: 10,
  source: 'releve-mbc.pdf',
  detected_format: 'cegid_weekly',
  detected_scope: 'weekly',
  warnings: [],
  employees: [
    {
      raw_name: 'EXEMPLE Jean',
      employee_id: null,
      matched_name: null,
      match_confidence: 'low',
      review_status: 'error',
      days: [{ jour: 21, heures: 7, type: 'travail', nature: 'reel', year: 2026, month: 9 }],
      warnings: [ANNOTATIONS],
    },
  ],
};

test('le relevé à relire se lit jour par jour, sans rien couper', async ({ page }) => {
  test.setTimeout(120_000);
  const s = surveiller(page);
  await page.route('**/api/schedules/assisted-fill/extract-timesheet/start', (route) =>
    route.fulfill({ status: 200, json: { job_id: 'e2e-job', status: 'queued' } }),
  );
  await page.route('**/api/schedules/assisted-fill/extract-timesheet/jobs/e2e-job', (route) => {
    if (route.request().method() !== 'GET') return route.fulfill({ status: 200, json: { status: 'cancelled', job_id: 'e2e-job' } });
    return route.fulfill({
      status: 200,
      json: {
        job_id: 'e2e-job',
        status: 'completed',
        progress: { phase: 'done', pages_total: 1, pages_done: 1, current_page: 1 },
        proposal: PROPOSITION,
      },
    });
  });

  await page.goto('/schedules');
  await page.getByRole('button', { name: 'Importer des pointages' }).click({ timeout: 45_000 });
  await page.locator('input[type="file"]').setInputFiles({
    name: 'releve-mbc.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 releve simule'),
  });
  await page.getByRole('button', { name: /Analyser/ }).click();

  // Sous la ligne du salarié : un jour par ligne, l'annotation entière.
  const ligne = page.getByTestId('annotations-releve-ligne');
  await expect(ligne).toBeVisible({ timeout: 60_000 });
  await expect(ligne.getByText('« CP »')).toBeVisible();
  await expect(ligne.getByText('« ?????? absent 7,5 »')).toBeVisible();
  await ligne.getByRole('button', { name: 'Voir les 2 autres jours' }).click();
  await expect(ligne.getByText('« +1 », badgeage incomplet, 3,53 h lues')).toBeVisible();

  // Le bandeau du haut regroupe tous les salariés, et se déplie.
  const bandeau = page.getByTestId('annotations-releve');
  await expect(bandeau.getByText(/5 jours annotés sur le relevé/)).toBeVisible();
  await bandeau.getByRole('button').click();
  await expect(bandeau.getByText('EXEMPLE Jean')).toBeVisible();
  await expect(bandeau.getByText('« PANIERS 3 »')).toBeVisible();
  await verifierPageSaine(page, s);
});
