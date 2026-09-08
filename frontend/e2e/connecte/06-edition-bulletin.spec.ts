import { test, expect, type Page } from '@playwright/test';

// Bulletin entièrement fictif : les lectures et écritures de ce bulletin sont
// interceptées. Aucun bulletin de la base partagée n'est modifié.
const BULLETIN_ID = '00000000-0000-4000-8000-000000000006';
const chemin = `/payslips/${BULLETIN_ID}/edit`;

async function preparerBulletin(page: Page, verrouille = false) {
  let bulletin = {
    id: BULLETIN_ID,
    employee_id: '00000000-0000-4000-8000-000000000007',
    company_id: '00000000-0000-4000-8000-000000000008',
    name: 'Bulletin fictif QA',
    month: 7,
    year: 2026,
    url: '',
    pdf_storage_path: '',
    manually_edited: false,
    manual_edit_locked: verrouille,
    manual_edit_lock_reason: verrouille ? 'Période verrouillée pour ce test' : null,
    edit_count: 0,
    internal_notes: [],
    edit_history: [],
    payslip_data: {
      en_tete: {},
      calcul_du_brut: [
        { libelle: 'Salaire de base QA', quantite: 100, taux: 10, gain: 1000 },
        { libelle: 'Heures suppl. majorées à 25%', quantite: 2, taux: 10, gain: 20 },
        { libelle: 'Heures suppl. majorées à 50%', quantite: 3.5, taux: 15, gain: 52.5 },
      ],
      salaire_brut: 1072.5,
      structure_cotisations: {
        bloc_principales: [], bloc_allegements: [], bloc_csg_non_deductible: [],
        total_salarial: 0, total_patronal: 0,
      },
      synthese_net: {
        net_social_avant_impot: 800,
        impot_prelevement_a_la_source: { base: 1000, taux: 5, montant: 50 },
        remboursement_transport: 0,
        indemnite_transport_fixe: 0,
      },
      net_a_payer: 750,
    },
  };
  const sauvegardes: Array<{
    payslip_data: typeof bulletin.payslip_data;
    changes_summary: string;
  }> = [];
  await page.route(`**/api/payslips/${BULLETIN_ID}{,/**}`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() === 'POST' && url.pathname.endsWith('/edit')) {
      const saisie = request.postDataJSON() as typeof sauvegardes[number];
      sauvegardes.push(saisie);
      bulletin = {
        ...bulletin,
        payslip_data: saisie.payslip_data,
        manually_edited: true,
        edit_count: bulletin.edit_count + 1,
      };
      await route.fulfill({ json: { success: true, payslip: bulletin } });
    } else if (request.method() === 'GET' && url.pathname.endsWith(BULLETIN_ID)) {
      await route.fulfill({ json: bulletin });
    } else {
      // Pas de repli réseau pour cet identifiant fictif.
      await route.fulfill({ status: 404, json: { detail: 'Route QA non prévue' } });
    }
  });
  await page.goto(chemin);
  await expect(page.getByRole('heading', { name: 'Édition du bulletin - Bulletin fictif QA' }))
    .toBeVisible({ timeout: 30_000 });
  return sauvegardes;
}

test.describe('Édition du bulletin (données fictives)', () => {
  test('les HS et le total restent cohérents après saisie, sauvegarde et réouverture', async ({ page }) => {
    const sauvegardes = await preparerBulletin(page);
    const ligne = page.getByRole('table').filter({ hasText: 'Salaire de base QA' }).getByRole('row').nth(2);
    await ligne.getByText('Heures suppl. majorées à 25%', { exact: true }).click();
    const quantite = ligne.getByRole('spinbutton').nth(0);
    await quantite.fill('');
    await expect(quantite).toHaveValue('');
    await quantite.fill('12.5');
    await quantite.press('Tab');
    await expect(quantite).toHaveValue('12.5');
    await expect(ligne.getByRole('spinbutton').nth(2)).toHaveValue('125');
    await expect(page.getByText('Total Brut: 1177.50 €', { exact: true })).toBeVisible();

    await page.locator('#changes-summary').fill('QA : correction de la quantité HS');
    await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
    await expect(page.locator('#changes-summary')).toHaveValue('');
    await expect(page.getByRole('button', { name: 'Enregistrer', exact: true })).toBeDisabled();
    expect(sauvegardes).toHaveLength(1);
    expect(sauvegardes[0].payslip_data.calcul_du_brut?.[1]).toMatchObject({ quantite: 12.5, gain: 125 });
    expect(sauvegardes[0].payslip_data.salaire_brut).toBe(1177.5);

    await page.reload();
    await expect(page.getByRole('row').filter({ hasText: 'Heures suppl. majorées à 25%' }))
      .toContainText('12.50');
    await expect(page.getByText('Total Brut: 1177.50 €', { exact: true })).toBeVisible();
  });

  test('ajout, modification et suppression de ligne conservent les autres saisies', async ({ page }) => {
    const sauvegardes = await preparerBulletin(page);
    const table = page.getByRole('table').filter({ hasText: 'Salaire de base QA' });
    await page.getByRole('button', { name: 'Ajouter une ligne', exact: true }).click();
    const ajout = table.getByRole('row').last();
    await ajout.getByText('Nouvelle ligne', { exact: true }).click();
    await ajout.getByRole('spinbutton').nth(0).fill('0.5');
    await ajout.getByRole('spinbutton').nth(1).fill('20');
    await expect(ajout.getByRole('spinbutton').nth(2)).toHaveValue('10');
    await expect(page.getByText('Total Brut: 1082.50 €', { exact: true })).toBeVisible();
    await ajout.getByRole('button').click();
    await expect(table.getByRole('row')).toHaveCount(4);
    await expect(page.getByText('Total Brut: 1072.50 €', { exact: true })).toBeVisible();

    // Même mécanisme de mise à jour utilisé par la synthèse du net.
    await page.locator('#net_social').fill('825');
    await page.locator('#net_social').press('Tab');
    await expect(page.locator('#net_social')).toHaveValue('825');
    await page.locator('#changes-summary').fill('QA : modification de la synthèse');
    await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
    await expect(page.locator('#changes-summary')).toHaveValue('');
    await expect(page.getByRole('button', { name: 'Enregistrer', exact: true })).toBeDisabled();
    expect(sauvegardes).toHaveLength(1);
    expect(sauvegardes[0].payslip_data.calcul_du_brut).toHaveLength(3);
    expect(sauvegardes[0].payslip_data.synthese_net?.net_social_avant_impot).toBe(825);
    expect(sauvegardes[0].payslip_data.net_a_payer).toBe(775);
  });

  test('un bulletin verrouillé reste non modifiable', async ({ page }) => {
    const sauvegardes = await preparerBulletin(page, true);
    await expect(page.getByText('Période verrouillée pour ce test', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Enregistrer', exact: true })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Ajouter une ligne', exact: true })).toBeDisabled();
    const ligne = page.getByRole('table').filter({ hasText: 'Salaire de base QA' }).getByRole('row').nth(2);
    await ligne.getByText('Heures suppl. majorées à 25%', { exact: true }).click();
    await expect(ligne.getByRole('spinbutton').nth(0)).toBeDisabled();
    expect(sauvegardes).toHaveLength(0);
  });
});

test.describe('Ce que l’écran annonce selon la ligne corrigée', () => {
  function ligneDuBrut(page: Page, rang: number) {
    return page
      .getByRole('table')
      .filter({ hasText: 'Salaire de base QA' })
      .getByRole('row')
      .nth(rang);
  }

  test('corriger des heures supplémentaires annonce un recalcul complet', async ({
    page,
  }) => {
    await preparerBulletin(page);
    const info = page.getByTestId('info-recalcul-heures-sup');
    const avertissement = page.getByTestId('avertissement-recalcul-brut');
    await expect(info).toBeHidden();

    const ligne = ligneDuBrut(page, 2);
    await ligne.getByText('Heures suppl. majorées à 25%', { exact: true }).click();
    await ligne.getByRole('spinbutton').nth(0).fill('12.5');
    await ligne.getByRole('spinbutton').nth(0).press('Tab');

    await expect(info).toBeVisible();
    await expect(info).toContainText('Le bulletin sera recalculé');
    // Pas d'alarme : sa correction suffit, le serveur refait le bulletin.
    await expect(avertissement).toBeHidden();
  });

  test('corriger une autre ligne prévient que le net ne suit pas', async ({ page }) => {
    await preparerBulletin(page);
    const avertissement = page.getByTestId('avertissement-recalcul-brut');
    await expect(avertissement).toBeHidden();

    // Filtre sur l'en-tête : passer une ligne en édition remplace son libellé
    // par un champ, et un filtre sur ce libellé cesserait alors de matcher.
    const ligne = page
      .getByRole('table')
      .filter({ hasText: 'Base/Qté' })
      .getByRole('row')
      .nth(1);
    await ligne.getByText('Salaire de base QA', { exact: true }).click();
    await ligne.getByRole('spinbutton').nth(0).fill('99');
    await ligne.getByRole('spinbutton').nth(0).press('Tab');

    await expect(avertissement).toBeVisible();
    await expect(avertissement).toContainText('ne suivent pas cette ligne');
    await expect(page.getByTestId('info-recalcul-heures-sup')).toBeHidden();
  });

  test('ajouter une ligne prévient aussi', async ({ page }) => {
    await preparerBulletin(page);
    await expect(page.getByTestId('avertissement-recalcul-brut')).toBeHidden();
    await page.getByRole('button', { name: 'Ajouter une ligne', exact: true }).click();
    await expect(page.getByTestId('avertissement-recalcul-brut')).toBeVisible();
  });
});

test.describe('Corriger à la source plutôt que patcher le bulletin', () => {
  test('le bouton d’en-tête mène aux variables du mois, filtrées sur le salarié', async ({ page }) => {
    await preparerBulletin(page);
    await page.getByTestId('corriger-les-variables').click();
    await expect(page).toHaveURL(new RegExp('/saisies\\?year=2026&month=7&employee='));
    await expect(page.getByTestId('filtre-salarie-primes')).toBeVisible();
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
    expect(appels[0]).toMatchObject({
      employee_id: '00000000-0000-4000-8000-000000000007',
      year: 2026,
      month: 7,
    });
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
    await preparerBulletin(page, true);
    await expect(page.getByTestId('regenerer-bulletin')).toBeDisabled();
  });
});
