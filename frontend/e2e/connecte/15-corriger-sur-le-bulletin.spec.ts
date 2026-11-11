import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';

// Bulletin entièrement fictif : les lectures et écritures de ce bulletin sont
// interceptées. Aucun bulletin de la base partagée n'est modifié.
const BULLETIN_ID = '00000000-0000-4000-8000-000000000015';
const SALARIE_ID = '00000000-0000-4000-8000-000000000016';
const chemin = `/payslips/${BULLETIN_ID}/edit`;

type Corps = {
  corrections: Record<string, unknown>;
  pdf_notes?: string;
  internal_note?: string;
  changes_summary?: string;
  base_updated_at?: string;
};

const LIGNES = {
  lignes: [
    { code: 'brut:salaire_base', bloc: 'brut', libelle: 'Salaire de base QA', mode: 'base_ou_taux', base: 100, taux: 10, montant: 1000 },
    { code: 'brut:prime_anciennete', bloc: 'brut', libelle: 'Prime d’ancienneté QA', mode: 'montant', montant: 58.2 },
    { code: 'brut:maintien_employeur', bloc: 'brut', libelle: 'Maintien de salaire employeur', mode: 'montant', montant: 312.44 },
    { code: 'brut:saisie:saisie-qa-1', bloc: 'brut', libelle: 'Prime de chantier QA', mode: null, montant: 100 },
    {
      code: 'cotisation:vieillesse_qa', bloc: 'cotisations', libelle: 'Vieillesse QA', mode: 'base_ou_taux',
      base: 1177.5, taux_salarial: 0.069, taux_patronal: 0.0855, montant_salarial: 81.25, montant_patronal: 100.68,
    },
  ],
  en_attente: [],
  a_la_source: [],
};

const HISTORIQUE = [
  {
    version: 3,
    edited_at: '2026-11-11T08:00:00+00:00',
    edited_by: null,
    edited_by_name: null,
    changes_summary: '',
    previous_payslip_data: { net_a_payer: 900 },
  },
];

type Options = {
  verrouille?: boolean;
  statut?: 'brouillon' | 'valide';
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
      en_tete: { salarie: { prenom: 'Jeanne', nom: 'Essai' } },
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
  const restaurations: Array<Record<string, unknown>> = [];
  await page.route(`**/api/payslips/${BULLETIN_ID}{,/**}`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() === 'POST' && url.pathname.endsWith('/edit')) {
      const corps = request.postDataJSON() as Corps;
      envois.push(corps);
      // Même `updated_at` que la lecture : la barre de résultat n'apparaît que pour la version courante.
      await route.fulfill({
        json: {
          status: 'success',
          message: 'Bulletin corrigé et recalculé.',
          // La version 3 de l'historique est celle de cette application : « Annuler » la remet.
          payslip: {
            ...bulletin,
            payslip_data: { ...bulletin.payslip_data, net_a_payer: 912.34 },
            edit_history: [HISTORIQUE[0]],
          },
          recalcule: Object.keys(corps.corrections).length > 0,
          recalcul_erreur: null,
        },
      });
    } else if (request.method() === 'POST' && url.pathname.endsWith('/restore')) {
      restaurations.push(request.postDataJSON() as Record<string, unknown>);
      await route.fulfill({
        json: { status: 'success', message: 'Version rétablie.', payslip: bulletin, recalcule: true },
      });
    } else if (request.method() === 'POST' && url.pathname.endsWith('/preview')) {
      await route.fulfill({ json: { html: '<p>Aperçu QA</p>' } });
    } else if (request.method() === 'GET' && url.pathname.endsWith('/lignes-corrigeables')) {
      await route.fulfill({ json: LIGNES });
    } else if (request.method() === 'GET' && url.pathname.endsWith('/history')) {
      await route.fulfill({
        json: HISTORIQUE,
      });
    } else if (request.method() === 'GET' && url.pathname.endsWith(BULLETIN_ID)) {
      await route.fulfill({ json: bulletin });
    } else {
      // Pas de repli réseau pour cet identifiant fictif.
      await route.fulfill({ status: 404, json: { detail: 'Route QA non prévue' } });
    }
  });
  // Lectures annexes de l'écran, toutes sur le salarié fictif : rien ne part
  // vers la base partagée avec cet identifiant.
  await page.route(`**/api/employees/${SALARIE_ID}{,/**}`, async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() !== 'GET') return route.fallback();
    if (url.pathname.endsWith('/monthly-inputs') || url.pathname.endsWith('/payslips')) {
      await route.fulfill({ json: [] });
    } else {
      await route.fulfill({
        json: { id: SALARIE_ID, first_name: 'Jeanne', last_name: 'Essai', is_forfait_jour: false },
      });
    }
  });
  await page.goto(chemin);
  await expect(page.getByRole('heading', { name: 'Bulletin de juillet 2026 — Jeanne Essai' }))
    .toBeVisible({ timeout: 30_000 });
  await page.getByRole('tab', { name: 'Corriger', exact: true }).click();
  await expect(page.getByTestId('bandeau-etapes')).toBeVisible();
  return { envois, restaurations };
}

test.describe('Corriger sur le bulletin (données fictives)', () => {
  test('corriger un montant : crayon, valeur, motif, appliquer, net avant/après', async ({ page }) => {
    const { envois } = await preparerBulletin(page);
    await expect(page.getByTestId('etape-1')).toHaveAttribute('data-etat', 'en-cours');
    await page.getByTestId('corriger-brut:prime_anciennete').click();
    await expect(page.getByTestId('etape-2')).toHaveAttribute('data-etat', 'en-cours');
    await page.getByTestId('valeur-brut:prime_anciennete').fill('63');
    await expect(page.getByTestId('apercu-brut:prime_anciennete')).toContainText('63,00');
    await page.getByTestId('motif-brut:prime_anciennete').getByRole('button', { name: 'Correction d’une erreur de calcul' }).click();
    await expect(page.getByTestId('barre-enregistrement')).toContainText('1 changement à appliquer');
    await page.getByTestId('enregistrer-barre').click();
    await expect(page.getByTestId('resultat-application')).toContainText('900,00');
    await expect(page.getByTestId('resultat-application')).toContainText('912,34');
    expect(envois[0].corrections).toMatchObject({
      corrections_ajoutees: [{ ligne: 'brut:prime_anciennete', montant: 63, motif: 'Correction d’une erreur de calcul' }],
    });
  });

  test('retirer une ligne calculée demande un motif, la ligne reste barrée et se remet', async ({ page }) => {
    await preparerBulletin(page);
    await page.getByTestId('retirer-brut:maintien_employeur').click();
    await page.getByTestId('motif-retrait-brut:maintien_employeur').getByRole('button', { name: 'Ligne non due ce mois-ci' }).click();
    await expect(page.getByTestId('ligne-brut:maintien_employeur')).toContainText('Retirée');
    await page.getByTestId('remettre-brut:maintien_employeur').click();
    await expect(page.getByTestId('ligne-brut:maintien_employeur')).not.toContainText('Retirée');
  });

  test('retirer une prime saisie', async ({ page }) => {
    const { envois } = await preparerBulletin(page);
    await page.getByTestId('retirer-prime-saisie-qa-1').click();
    await expect(page.getByTestId('prime-saisie-qa-1')).toContainText('Retirée');
    await page.getByTestId('enregistrer-barre').click();
    await expect(page.getByTestId('resultat-application')).toBeVisible();
    expect(envois[0].corrections).toMatchObject({ primes_retirees: ['saisie-qa-1'] });
  });

  test('ajouter des heures sup du mois par la tuile « Des heures »', async ({ page }) => {
    const { envois } = await preparerBulletin(page);
    await page.getByTestId('ajouter-une-ligne').click();
    await page.getByTestId('tuile-heures').click();
    await page.getByTestId('heures-sup-25').fill('4');
    await expect(page.getByTestId('lignes-ajoutees')).toContainText('4 h à 25 %');
    await page.getByTestId('enregistrer-barre').click();
    await expect(page.getByTestId('resultat-application')).toBeVisible();
    expect(envois[0].corrections).toHaveProperty('heures_sup');
  });

  test('ajouter un remboursement sur le net', async ({ page }) => {
    const { envois } = await preparerBulletin(page);
    await page.getByTestId('ajouter-une-ligne').click();
    await page.getByTestId('tuile-net').click();
    await page.getByLabel('Libellé sur le bulletin').fill('Remboursement QA');
    await page.getByLabel('Montant (€)').fill('25');
    await page.getByTestId('ajouter-sur-le-net').click();
    await expect(page.getByTestId('lignes-ajoutees')).toContainText('Remboursement QA');
    await page.getByTestId('enregistrer-barre').click();
    await expect(page.getByTestId('resultat-application')).toBeVisible();
    expect(envois[0].corrections).toMatchObject({ primes_ajoutees: [{ name: 'Remboursement QA', sur_le_net: true }] });
  });

  test('annuler après application remet la dernière version', async ({ page }) => {
    const { restaurations } = await preparerBulletin(page);
    await page.getByTestId('retirer-prime-saisie-qa-1').click();
    await page.getByTestId('enregistrer-barre').click();
    await page.getByTestId('annuler-application').click();
    await expect(page.getByText('Correction annulée', { exact: true })).toBeVisible();
    expect(restaurations[0]).toEqual({ version: 3 });
  });

  test('valeur sans motif : la ligne et la barre disent le motif manquant', async ({ page }) => {
    await preparerBulletin(page);
    await page.getByTestId('corriger-brut:prime_anciennete').click();
    await page.getByTestId('valeur-brut:prime_anciennete').fill('63');
    await expect(page.getByTestId('ligne-brut:prime_anciennete')).toContainText('Motif manquant');
    await expect(page.getByTestId('aide-motif-brut:prime_anciennete')).toContainText('Choisissez un motif');
    await expect(page.getByTestId('lignes-sans-motif')).toContainText('1 ligne ouverte sans motif');
    await expect(page.getByTestId('etape-2')).toHaveAttribute('data-etat', 'en-cours');
    // Le motif choisi : la ligne est prête, la phrase de la barre s'en va.
    await page.getByTestId('motif-brut:prime_anciennete').getByRole('button', { name: 'Correction d’une erreur de calcul' }).click();
    await expect(page.getByTestId('lignes-sans-motif')).toHaveCount(0);
    await expect(page.getByTestId('barre-enregistrement')).toContainText('1 changement à appliquer');
  });

  test('une ligne prête (valeur et motif) passe à l’étape 3, éditeur encore ouvert', async ({ page }) => {
    await preparerBulletin(page);
    await page.getByTestId('corriger-brut:prime_anciennete').click();
    await page.getByTestId('valeur-brut:prime_anciennete').fill('63');
    await expect(page.getByTestId('etape-2')).toHaveAttribute('data-etat', 'en-cours');
    await page.getByTestId('motif-brut:prime_anciennete').getByRole('button', { name: 'Correction d’une erreur de saisie' }).click();
    await expect(page.getByTestId('valeur-brut:prime_anciennete')).toBeVisible();
    await expect(page.getByTestId('etape-3')).toHaveAttribute('data-etat', 'en-cours');
    await expect(page.getByTestId('etape-2')).toHaveAttribute('data-etat', 'faite');
  });

  test('corriger une cotisation au crayon : le bloc des cotisations reste ouvert pendant la saisie', async ({ page }) => {
    const { envois } = await preparerBulletin(page);
    const bloc = page.getByTestId('bloc-cotisations');
    await expect(bloc).toHaveJSProperty('open', false);
    await bloc.locator('summary').click();
    await expect(bloc).toHaveJSProperty('open', true);
    await page.getByTestId('corriger-cotisation:vieillesse_qa').click();
    await page.getByTestId('valeur-cotisation:vieillesse_qa').fill('1200');
    await page.getByTestId('motif-cotisation:vieillesse_qa').getByRole('button', { name: 'Correction d’une erreur de calcul' }).click();
    await expect(bloc).toHaveJSProperty('open', true);
    // Effacer puis retaper : la correction part puis revient, le bloc ne se replie pas.
    await page.getByTestId('valeur-cotisation:vieillesse_qa').fill('');
    await expect(bloc).toHaveJSProperty('open', true);
    await page.getByTestId('valeur-cotisation:vieillesse_qa').fill('1250');
    await expect(bloc).toHaveJSProperty('open', true);
    await expect(page.getByTestId('apercu-cotisation:vieillesse_qa')).toBeVisible();
    await page.getByTestId('enregistrer-barre').click();
    await expect(page.getByTestId('resultat-application')).toBeVisible();
    expect(envois[0].corrections).toMatchObject({
      corrections_ajoutees: [{ ligne: 'cotisation:vieillesse_qa', base: 1250, motif: 'Correction d’une erreur de calcul' }],
    });
  });
});
