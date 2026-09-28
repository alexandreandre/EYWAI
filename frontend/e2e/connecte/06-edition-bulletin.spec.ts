import { test, expect, type Page } from '@playwright/test';

// Bulletin entièrement fictif : les lectures et écritures de ce bulletin sont
// interceptées. Aucun bulletin de la base partagée n'est modifié.
const BULLETIN_ID = '00000000-0000-4000-8000-000000000006';
const SALARIE_ID = '00000000-0000-4000-8000-000000000007';
const chemin = `/payslips/${BULLETIN_ID}/edit`;

type Corps = {
  corrections: Record<string, unknown>;
  pdf_notes?: string;
  internal_note?: string;
  changes_summary?: string;
  base_updated_at?: string;
};

type Options = {
  verrouille?: boolean;
  statut?: 'brouillon' | 'valide';
  /** Réponse du serveur à l'enregistrement (statut HTTP et corps). */
  repondre?: (corps: Corps) => { status?: number; json: unknown };
};

function bulletinFictif(options: Options) {
  return {
    id: BULLETIN_ID,
    employee_id: SALARIE_ID,
    company_id: '00000000-0000-4000-8000-000000000008',
    name: 'Bulletin fictif QA',
    month: 7,
    year: 2026,
    url: '',
    pdf_storage_path: '',
    status: options.statut ?? 'brouillon',
    updated_at: '2026-09-28T09:00:00+00:00',
    manually_edited: false,
    manual_edit_locked: Boolean(options.verrouille),
    manual_edit_lock_reason: options.verrouille ? 'Période verrouillée pour ce test' : null,
    edit_count: 0,
    internal_notes: [],
    edit_history: [],
    exports_du_mois: [],
    a_regenerer: null,
    pdf_notes: null,
    payslip_data: {
      en_tete: {},
      calcul_du_brut: [
        { libelle: 'Salaire de base QA', quantite: 100, taux: 10, gain: 1000 },
        { libelle: 'Heures suppl. majorées à 25%', quantite: 2, taux: 12.5, gain: 25 },
        { libelle: 'Heures suppl. majorées à 50%', quantite: 3.5, taux: 15, gain: 52.5 },
        { libelle: 'Prime de chantier QA', gain: 100, saisie_id: 'saisie-qa-1' },
      ],
      primes_non_soumises: [{ libelle: 'Panier QA', montant: 7.5, saisie_id: 'saisie-qa-2' }],
      salaire_brut: 1177.5,
      net_a_payer: 900,
    },
  };
}

async function preparerBulletin(page: Page, options: Options = {}) {
  const bulletin = bulletinFictif(options);
  const envois: Corps[] = [];
  await page.route(`**/api/payslips/${BULLETIN_ID}{,/**}`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() === 'POST' && url.pathname.endsWith('/edit')) {
      const corps = request.postDataJSON() as Corps;
      envois.push(corps);
      const reponse = options.repondre?.(corps) ?? {
        json: {
          status: 'success',
          message: 'Bulletin corrigé et recalculé.',
          payslip: bulletin,
          recalcule: Object.keys(corps.corrections).length > 0,
          recalcul_erreur: null,
        },
      };
      await route.fulfill({ status: reponse.status ?? 200, json: reponse.json });
    } else if (request.method() === 'POST' && url.pathname.endsWith('/preview')) {
      await route.fulfill({ json: { html: '<p>Aperçu QA</p>' } });
    } else if (request.method() === 'GET' && url.pathname.endsWith(BULLETIN_ID)) {
      await route.fulfill({ json: bulletin });
    } else {
      // Pas de repli réseau pour cet identifiant fictif.
      await route.fulfill({ status: 404, json: { detail: 'Route QA non prévue' } });
    }
  });
  await page.goto(chemin);
  await expect(page.getByRole('heading', { name: 'Corriger le bulletin - Bulletin fictif QA' }))
    .toBeVisible({ timeout: 30_000 });
  return envois;
}

test.describe('Corriger un bulletin par ses variables du mois (données fictives)', () => {
  test('rien à enregistrer tant que rien ne change', async ({ page }) => {
    await preparerBulletin(page);
    await expect(page.getByTestId('heures-sup-25')).toHaveValue('2');
    await expect(page.getByTestId('heures-sup-50')).toHaveValue('3.5');
    await expect(page.getByTestId('enregistrer-entete')).toBeDisabled();
    await expect(page.getByTestId('barre-enregistrement')).toBeHidden();
  });

  test('corriger les heures sup les déclare par palier et recalcule', async ({ page }) => {
    const envois = await preparerBulletin(page);
    await page.getByTestId('heures-sup-25').fill('4');
    await expect(page.getByTestId('barre-enregistrement')).toContainText('recalculé en entier');
    await page.getByTestId('enregistrer-barre').click();

    await expect(page.getByText('Bulletin corrigé et recalculé', { exact: true })).toBeVisible();
    expect(envois).toHaveLength(1);
    expect(envois[0].corrections).toEqual({ heures_sup: { hs25: 4, hs50: 3.5 } });
    expect(envois[0].base_updated_at).toBe('2026-09-28T09:00:00+00:00');
    expect(envois[0]).not.toHaveProperty('payslip_data');
  });

  test('ramener les heures sup à zéro est une vraie correction', async ({ page }) => {
    const envois = await preparerBulletin(page);
    await page.getByTestId('heures-sup-25').fill('0');
    await page.getByTestId('heures-sup-50').fill('');
    await page.getByTestId('enregistrer-entete').click();
    await expect(page.getByText('Bulletin corrigé et recalculé', { exact: true })).toBeVisible();
    expect(envois[0].corrections).toEqual({ heures_sup: { hs25: 0, hs50: 0 } });
  });

  test('reprendre les heures du planning', async ({ page }) => {
    const envois = await preparerBulletin(page);
    await page.getByTestId('revenir-au-planning').click();
    await expect(page.getByTestId('retour-planning')).toBeVisible();
    await page.getByTestId('enregistrer-entete').click();
    await expect(page.getByText('Bulletin corrigé et recalculé', { exact: true })).toBeVisible();
    expect(envois[0].corrections).toEqual({ revenir_au_planning: true });
  });

  test('corriger, retirer et ajouter une prime', async ({ page }) => {
    const envois = await preparerBulletin(page);
    await page.locator('#montant-saisie-qa-1').fill('150');
    await page.getByRole('button', { name: 'Retirer Panier QA' }).click();

    // Prime libre par « Créer une prime… », sans l'enregistrer au catalogue
    // (case décochée par défaut) : rien n'est écrit en base.
    await page.getByRole('button', { name: 'Ajouter une prime', exact: true }).click();
    const selecteur = page.getByRole('dialog', { name: 'Ajouter une Saisie du Mois' });
    await expect(selecteur).toBeVisible();
    await selecteur.getByPlaceholder('Sélectionnez ou saisissez un nom...').click();
    await page.getByRole('option', { name: 'Créer une prime...' }).click();
    await selecteur.getByPlaceholder("Ex: Prime d'assiduité").fill('Prime QA ajoutée');
    await selecteur.getByPlaceholder('0.00').fill('80');
    const caseCatalogue = selecteur.locator('#save_to_catalogue');
    if (await caseCatalogue.count()) await expect(caseCatalogue).not.toBeChecked();
    await selecteur.getByRole('button', { name: 'Enregistrer', exact: true }).click();
    await expect(selecteur).toBeHidden();

    await page.getByTestId('enregistrer-entete').click();
    await expect(page.getByText('Bulletin corrigé et recalculé', { exact: true })).toBeVisible();
    expect(envois[0].corrections).toMatchObject({
      primes_corrigees: [{ saisie_id: 'saisie-qa-1', amount: 150 }],
      primes_retirees: ['saisie-qa-2'],
      primes_ajoutees: [{ name: 'Prime QA ajoutée', amount: 80 }],
    });
  });

  test('seule la note change : enregistrée sans recalcul', async ({ page }) => {
    const envois = await preparerBulletin(page);
    await page.locator('#pdf-notes').fill('Note QA visible sur le bulletin');
    await expect(page.getByTestId('enregistrer-entete')).toHaveText(/Enregistrer les notes/);
    await page.getByTestId('enregistrer-entete').click();
    await expect(page.getByText('Notes enregistrées', { exact: true })).toBeVisible();
    expect(envois[0]).toMatchObject({ corrections: {}, pdf_notes: 'Note QA visible sur le bulletin' });
  });

  test('un recalcul en échec est dit, pas un succès', async ({ page }) => {
    await preparerBulletin(page, {
      repondre: () => ({
        json: {
          status: 'success',
          message: 'Corrections enregistrées',
          payslip: bulletinFictif({}),
          recalcule: false,
          recalcul_erreur: 'Barème introuvable',
        },
      }),
    });
    await page.getByTestId('heures-sup-25').fill('4');
    await page.getByTestId('enregistrer-entete').click();
    await expect(page.getByText('Corrections enregistrées, bulletin non recalculé', { exact: true }))
      .toBeVisible();
    await expect(page.getByText('Barème introuvable — utilisez « Régénérer ».', { exact: true }))
      .toBeVisible();
  });

  test('un bulletin modifié entre-temps est rechargé', async ({ page }) => {
    await preparerBulletin(page, {
      repondre: () => ({ status: 409, json: { detail: 'Le bulletin a changé depuis son ouverture.' } }),
    });
    await page.getByTestId('heures-sup-25').fill('4');
    await page.getByTestId('enregistrer-entete').click();
    await expect(page.getByText('Le bulletin a changé depuis son ouverture', { exact: true })).toBeVisible();
    await expect(page.getByTestId('heures-sup-25')).toHaveValue('2');
  });

  test('corriger un bulletin validé demande confirmation', async ({ page }) => {
    const envois = await preparerBulletin(page, { statut: 'valide' });
    await page.getByTestId('heures-sup-25').fill('4');
    await page.getByTestId('enregistrer-entete').click();
    const confirmation = page.getByRole('alertdialog', { name: 'Corriger un bulletin validé ?' });
    await expect(confirmation).toBeVisible();
    expect(envois).toHaveLength(0);
    await confirmation.getByRole('button', { name: 'Corriger et repasser en brouillon' }).click();
    await expect(page.getByText('Bulletin corrigé et recalculé', { exact: true })).toBeVisible();
    expect(envois).toHaveLength(1);
  });

  test('un bulletin verrouillé ne se corrige pas', async ({ page }) => {
    await preparerBulletin(page, { verrouille: true });
    await expect(page.getByTestId('heures-sup-25')).toBeDisabled();
    await expect(page.getByTestId('enregistrer-entete')).toBeDisabled();
  });
});

test.describe('Corriger à la source', () => {
  test('les saisies du mois s’ouvrent filtrées sur le salarié', async ({ page }) => {
    await preparerBulletin(page);
    await page.getByTestId('corriger-les-variables').click();
    await expect(page).toHaveURL(new RegExp('/saisies\\?year=2026&month=7&employee='));
    await expect(page.getByTestId('filtre-salarie-primes')).toBeVisible();
  });

  test('quitter avec des corrections en cours demande confirmation', async ({ page }) => {
    await preparerBulletin(page);
    await page.getByTestId('heures-sup-25').fill('4');
    let question = '';
    page.once('dialog', async (dialog) => {
      question = dialog.message();
      await dialog.dismiss();
    });
    await page.getByTestId('corriger-les-variables').click();
    expect(question).toContain('Vos corrections ne sont pas enregistrées');
    await expect(page).toHaveURL(new RegExp(chemin));
  });

  test('régénérer refait calculer le bulletin par le moteur', async ({ page }) => {
    const appels: Array<Record<string, unknown>> = [];
    await page.route('**/api/actions/generate-payslip', async (route) => {
      appels.push(route.request().postDataJSON() as Record<string, unknown>);
      await route.fulfill({
        json: { status: 'success', message: 'ok', download_url: '', warnings: [] },
      });
    });
    await preparerBulletin(page);

    await page.getByTestId('regenerer-bulletin').click();
    await page.getByRole('button', { name: 'Régénérer', exact: true }).last().click();

    await expect(page.getByText('Bulletin régénéré', { exact: true })).toBeVisible();
    expect(appels).toHaveLength(1);
    expect(appels[0]).toMatchObject({ employee_id: SALARIE_ID, year: 2026, month: 7 });
    // Aucun forçage sans confirmation explicite.
    expect(appels[0]).not.toHaveProperty('regenerer_bulletin_valide');
  });

  test('un bulletin validé n’est régénéré qu’après confirmation', async ({ page }) => {
    const appels: Array<Record<string, unknown>> = [];
    await page.route('**/api/actions/generate-payslip', async (route) => {
      const corps = route.request().postDataJSON() as Record<string, unknown>;
      appels.push(corps);
      if (!corps.regenerer_bulletin_valide) {
        await route.fulfill({
          status: 409,
          json: { detail: { code: 'bulletin_valide', message: 'Bulletin déjà validé.' } },
        });
        return;
      }
      await route.fulfill({
        json: { status: 'success', message: 'ok', download_url: '', warnings: [] },
      });
    });
    await preparerBulletin(page);

    await page.getByTestId('regenerer-bulletin').click();
    await page.getByRole('button', { name: 'Régénérer', exact: true }).last().click();

    await expect(page.getByText('Bulletin déjà validé.', { exact: true })).toBeVisible();
    expect(appels).toHaveLength(1);

    await page.getByRole('button', { name: /Régénérer \(archive/ }).click();
    await expect(page.getByText('Bulletin régénéré', { exact: true })).toBeVisible();
    expect(appels).toHaveLength(2);
    expect(appels[1]).toMatchObject({ regenerer_bulletin_valide: true });
  });

  test('un bulletin verrouillé ne peut pas être régénéré', async ({ page }) => {
    await preparerBulletin(page, { verrouille: true });
    await expect(page.getByTestId('regenerer-bulletin')).toBeDisabled();
  });
});
