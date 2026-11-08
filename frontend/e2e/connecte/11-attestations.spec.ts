import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

// Attestations à la demande (05/11/2026), vues par une gestionnaire de paie
// (« mode paie ») : le compte QA, administrateur plateforme, passe pour une
// gestionnaire en réécrivant /api/auth/me ; le serveur garde ses droits.
//
// Rien n'est écrit (garde anti-écriture) : la génération est simulée. La lettre
// réelle et le refus réel du serveur se vérifient à part, contre l'API
// déployée (voir le compte rendu du 05/11/2026).
//
// Un seul parcours, sur une seule page (voir 08-mode-paie : des tests séparés
// repartant de la même session se verraient refuser son renouvellement).

async function commeUneGestionnaireDePaie(page: Page) {
  await page.route('**/api/auth/me', async (route) => {
    const reponse = await route.fetch();
    const moi = await reponse.json();
    const enRh = (acces: Record<string, unknown> | null | undefined) =>
      acces ? { ...acces, role: 'rh' } : acces;
    await route.fulfill({
      response: reponse,
      json: {
        ...moi,
        is_platform_admin: false,
        is_super_admin: false,
        role: 'rh',
        active_company: enRh(moi.active_company),
        accessible_companies: (moi.accessible_companies ?? []).map(enRh),
      },
    });
  });
}

async function enTetes(page: Page) {
  const { jeton, societe } = await page.evaluate(() => ({
    jeton: localStorage.getItem('authToken'),
    societe: localStorage.getItem('activeCompanyId'),
  }));
  return { Authorization: `Bearer ${jeton}`, ...(societe ? { 'X-Active-Company': societe } : {}) };
}

test.use({ storageState: { cookies: [], origins: [] } });

async function seConnecter(page: Page) {
  await page.goto('/login');
  await page.locator('#login-username').fill(process.env.E2E_QA_EMAIL!);
  await page.locator('#login-password').fill(process.env.E2E_QA_PASSWORD!);
  await page.getByRole('button', { name: /se connecter/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 30_000 });
}

async function choisir(page: Page, fenetre: ReturnType<Page['getByRole']>, champ: RegExp, option: RegExp) {
  await fenetre.getByLabel(champ).click();
  await page.getByRole('option', { name: option }).click();
}

test('attestations : fiche du salarié en mode paie, puis Exports', async ({ page }) => {
  test.setTimeout(180_000);
  await commeUneGestionnaireDePaie(page);
  await page.addInitScript(() => localStorage.removeItem('martine-rq-cache-v2'));
  await seConnecter(page);
  await page.route('**/api/client-errors', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    await route.fulfill({ status: 204, body: '' });
  });
  const s = surveiller(page);

  // Génération simulée : une attestation d'emploi produite, une lettre de salaire
  // refusée comme le fait le serveur quand aucun bulletin n'est remis.
  const ID_SIMULE = '00000000-0000-4000-8000-0000000000a1';
  const demandes: Array<Record<string, unknown>> = [];
  let documentSimule: Record<string, unknown> | null = null;
  await page.route('**/api/documents/generate', async (route) => {
    const corps = route.request().postDataJSON() as Record<string, unknown>;
    demandes.push(corps);
    if (corps.document_type === 'attestation_salaire') {
      await route.fulfill({
        status: 400,
        json: {
          detail:
            "Aucun bulletin remis à Jeanne Essai : Martine n'atteste que des salaires de bulletins validés et remis.",
        },
      });
      return;
    }
    const maintenant = new Date().toISOString();
    documentSimule = {
      id: ID_SIMULE,
      company_id: '',
      employee_id: corps.employee_id,
      document_type: corps.document_type,
      category: 'attestation_courante',
      template_id: null,
      template_version_id: null,
      is_eywai_template: true,
      file_url: null,
      file_name: 'attestation_d_emploi.pdf',
      status: 'brouillon',
      generation_context: {},
      generated_by: null,
      created_at: maintenant,
      updated_at: maintenant,
    };
    await route.fulfill({ status: 201, json: documentSimule });
  });
  await page.route(`**/api/documents/${ID_SIMULE}/preview`, async (route) => {
    await route.fulfill({
      json: { signed_url: 'https://stockage.invalid/attestation.pdf', file_name: 'attestation_d_emploi.pdf' },
    });
  });
  await page.route('https://stockage.invalid/**', async (route) => {
    await route.fulfill({
      contentType: 'application/pdf',
      body: '%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 200 200]/Parent 2 0 R>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF',
    });
  });
  // La liste des documents du salarié montre la lettre simulée une fois produite.
  await page.route(/\/api\/documents\/\?/, async (route) => {
    if (route.request().method() !== 'GET' || !documentSimule) return route.fallback();
    const reponse = await route.fetch();
    const liste = (await reponse.json()) as unknown[];
    await route.fulfill({ response: reponse, json: [documentSimule, ...liste] });
  });

  try {
    // La société active n'est connue qu'après le premier écran chargé.
    await page.goto('/payroll');
    await expect(page.getByText(/gestion de la paie/i).first()).toBeVisible({ timeout: 30_000 });
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem('activeCompanyId')), { timeout: 15_000 })
      .toBeTruthy();
    const reponse = await page.request.get(`${API_URL}/api/employees?limit=500`, {
      headers: await enTetes(page),
    });
    expect(reponse.ok(), `liste des salariés : ${reponse.status()} ${(await reponse.text()).slice(0, 200)}`).toBeTruthy();
    const salaries = (await reponse.json()) as Array<{ id: string; employment_status?: string | null }>;
    const salarie = salaries.find((e) => (e.employment_status ?? 'actif') === 'actif');
    expect(salarie, 'un salarié actif sur le test').toBeTruthy();

    await test.step('fiche > Documents : le bloc Attestations est là, en mode paie', async () => {
      await page.goto(`/employees/${salarie!.id}?tab=documents`);
      const bloc = page.getByRole('region', { name: 'Attestations' });
      await expect(bloc).toBeVisible({ timeout: 30_000 });
      await expect(page.getByText(/hors du périmètre paie/i)).toBeVisible();
      // Le contrat signé se dépose en mode paie : une fiche s'y complète sans nous.
      await expect(page.getByRole('region', { name: 'Contrat de travail' })).toBeVisible();
    });

    await test.step("attestation d'emploi : la lettre se génère et s’ouvre", async () => {
      await page.getByRole('region', { name: 'Attestations' }).getByRole('button', { name: /générer une attestation/i }).click();
      const fenetre = page.getByRole('dialog', { name: /générer une attestation/i });
      await expect(fenetre).toBeVisible();
      await expect(fenetre.getByText(/signataire réglé dans Entreprise > Fiche/i)).toBeVisible();
      await choisir(page, fenetre, /type d'attestation/i, /^attestation d'emploi$/i);
      await expect(fenetre.getByLabel(/nombre de mois/i)).toHaveCount(0);
      await fenetre.getByRole('button', { name: /^générer$/i }).click();
      await expect(page.getByText(/attestation d'emploi de .+ prête/i).first()).toBeVisible();
      expect(demandes.at(-1)).toEqual({
        employee_id: salarie!.id,
        document_type: 'attestation_emploi',
        category: 'attestation_courante',
        template_id: null,
      });
      await expect(page.getByRole('dialog', { name: /attestation d'emploi/i })).toBeVisible({ timeout: 30_000 });
      await page.keyboard.press('Escape');
      await expect(
        page.getByRole('region', { name: 'Attestations' }).getByText("Attestation d'emploi").first(),
      ).toBeVisible({ timeout: 15_000 });
    });

    await test.step('attestation de salaire : 3 mois par défaut, refus sans bulletin remis', async () => {
      await page.getByRole('region', { name: 'Attestations' }).getByRole('button', { name: /générer une attestation/i }).click();
      const fenetre = page.getByRole('dialog', { name: /générer une attestation/i });
      await choisir(page, fenetre, /type d'attestation/i, /^attestation de salaire$/i);
      await expect(fenetre.getByLabel(/nombre de mois/i)).toHaveValue('3');
      await fenetre.getByRole('button', { name: /^générer$/i }).click();
      // Le refus reste dans la fenêtre, qui reste ouverte.
      await expect(fenetre.getByRole('alert')).toContainText(/aucun bulletin remis à .+ : Martine n'atteste/i);
      await expect(fenetre).toBeVisible();
      expect(demandes.at(-1)).toMatchObject({ document_type: 'attestation_salaire', nombre_mois: 3 });
      await fenetre.getByRole('button', { name: /annuler/i }).click();
    });

    await test.step('Exports > Déclarations : la carte ouvre la même fenêtre, avec la liste des salariés', async () => {
      await page.goto('/exports');
      await page.getByRole('tab', { name: /déclarations/i }).click();
      await expect(page.getByText('Récapitulatif des salaires du mois').first()).toBeVisible({ timeout: 30_000 });
      await page.getByRole('button', { name: /générer une attestation/i }).click();
      const fenetre = page.getByRole('dialog', { name: /générer une attestation/i });
      await expect(fenetre.getByLabel(/^salarié$/i)).toBeVisible();
      await fenetre.getByLabel(/^salarié$/i).click();
      await expect(page.getByRole('option').first()).toBeVisible({ timeout: 15_000 });
      await page.keyboard.press('Escape');
      await fenetre.getByRole('button', { name: /annuler/i }).click();
    });

    // Le refus de l'attestation de salaire (400) est attendu : le navigateur
    // l'inscrit dans la console. Lui seul est écarté, nommément.
    s.erreurs = s.erreurs.filter((e) => !/status of 400 .*\/api\/documents\/generate/.test(e));
    await verifierPageSaine(page, s);
  } finally {
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  }
});

test('attestations : page Documents et fiche du salarié, hors mode paie', async ({ page }) => {
  test.setTimeout(120_000);
  await page.addInitScript(() => localStorage.removeItem('martine-rq-cache-v2'));
  await seConnecter(page);
  await page.route('**/api/client-errors', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    await route.fulfill({ status: 204, body: '' });
  });
  const s = surveiller(page);

  const ouvrirLaFenetre = async () => {
    await page.getByRole('button', { name: /ajouter un document/i }).click();
    await page.getByRole('menuitem', { name: /générer une attestation/i }).click();
    const fenetre = page.getByRole('dialog', { name: /générer une attestation/i });
    await expect(fenetre).toBeVisible();
    return fenetre;
  };
  const deuxTypesSeulement = async (fenetre: ReturnType<Page['getByRole']>) => {
    await fenetre.getByLabel(/type d'attestation/i).click();
    await expect(page.getByRole('option')).toHaveText(["Attestation d'emploi", 'Attestation de salaire']);
    await page.keyboard.press('Escape');
    await fenetre.getByRole('button', { name: /annuler/i }).click();
    await expect(fenetre).toHaveCount(0);
  };

  try {
    await test.step('page Documents : la fenêtre propose la liste des salariés et deux types', async () => {
      await page.goto('/documents');
      await expect(page.getByRole('button', { name: /ajouter un document/i })).toBeVisible({ timeout: 30_000 });
      const fenetre = await ouvrirLaFenetre();
      await fenetre.getByLabel(/^salarié$/i).click();
      await expect(page.getByRole('option').first()).toBeVisible({ timeout: 15_000 });
      await page.keyboard.press('Escape');
      await deuxTypesSeulement(fenetre);
    });

    await test.step('fiche du salarié : le salarié est connu, deux types', async () => {
      await expect
        .poll(() => page.evaluate(() => localStorage.getItem('activeCompanyId')), { timeout: 15_000 })
        .toBeTruthy();
      const reponse = await page.request.get(`${API_URL}/api/employees?limit=500`, { headers: await enTetes(page) });
      expect(reponse.ok()).toBeTruthy();
      const salaries = (await reponse.json()) as Array<{ id: string; employment_status?: string | null }>;
      const salarie = salaries.find((e) => (e.employment_status ?? 'actif') === 'actif');
      await page.goto(`/employees/${salarie!.id}?tab=documents`);
      await expect(page.getByRole('button', { name: /ajouter un document/i })).toBeVisible({ timeout: 30_000 });
      const fenetre = await ouvrirLaFenetre();
      await expect(fenetre.getByLabel(/^salarié$/i)).toHaveCount(0);
      await deuxTypesSeulement(fenetre);
    });

    await verifierPageSaine(page, s);
  } finally {
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  }
});
