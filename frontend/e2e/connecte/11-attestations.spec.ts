import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

// Attestations à la demande (05/11/2026), vues par une gestionnaire de paie
// (« mode paie ») : le compte QA, administrateur plateforme, passe pour une
// gestionnaire en réécrivant /api/auth/me ; le serveur garde ses droits.
//
// Le parcours écrit une seule chose, l'attestation de travail générée sur le
// test, et la supprime à la fin : tout est remis en état.
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
  const aSupprimer: string[] = [];

  try {
    const reponse = await page.request.get(`${API_URL}/api/employees?limit=500`, {
      headers: await enTetes(page),
    });
    expect(reponse.ok()).toBeTruthy();
    const salaries = (await reponse.json()) as Array<{ id: string; employment_status?: string | null }>;
    const salarie = salaries.find((e) => (e.employment_status ?? 'actif') === 'actif');
    expect(salarie, 'un salarié actif sur le test').toBeTruthy();

    await test.step('fiche > Documents : le bloc Attestations est là, en mode paie', async () => {
      await page.goto(`/employees/${salarie!.id}?tab=documents`);
      const bloc = page.getByRole('region', { name: 'Attestations' });
      await expect(bloc).toBeVisible({ timeout: 30_000 });
      await expect(page.getByText(/hors du périmètre paie/i)).toBeVisible();
    });

    await test.step('attestation de travail : la lettre se génère et s’ouvre', async () => {
      await page.getByRole('region', { name: 'Attestations' }).getByRole('button', { name: /générer une attestation/i }).click();
      const fenetre = page.getByRole('dialog', { name: /générer une attestation/i });
      await expect(fenetre).toBeVisible();
      await expect(fenetre.getByText(/signataire réglé dans Entreprise > Fiche/i)).toBeVisible();
      await choisir(page, fenetre, /type d'attestation/i, /^attestation de travail$/i);
      await expect(fenetre.getByLabel(/nombre de mois/i)).toHaveCount(0);
      const generation = page.waitForResponse(
        (r) => r.url().includes('/api/documents/generate') && r.request().method() === 'POST',
      );
      await fenetre.getByRole('button', { name: /^générer$/i }).click();
      const reponseGeneration = await generation;
      expect(reponseGeneration.status(), await reponseGeneration.text()).toBe(201);
      const doc = (await reponseGeneration.json()) as { id: string; document_type: string };
      aSupprimer.push(doc.id);
      expect(doc.document_type).toBe('attestation_emploi');
      await expect(page.getByText(/attestation de travail de .+ prête/i).first()).toBeVisible();
      await expect(page.getByRole('dialog', { name: /attestation de travail/i })).toBeVisible({ timeout: 30_000 });
      await page.keyboard.press('Escape');
      await expect(
        page.getByRole('region', { name: 'Attestations' }).getByText('Attestation de travail').first(),
      ).toBeVisible({ timeout: 15_000 });
    });

    await test.step('attestation de salaire : 3 mois par défaut, refus sans bulletin remis', async () => {
      await page.getByRole('region', { name: 'Attestations' }).getByRole('button', { name: /générer une attestation/i }).click();
      const fenetre = page.getByRole('dialog', { name: /générer une attestation/i });
      await choisir(page, fenetre, /type d'attestation/i, /^attestation de salaire$/i);
      await expect(fenetre.getByLabel(/nombre de mois/i)).toHaveValue('3');
      const generation = page.waitForResponse(
        (r) => r.url().includes('/api/documents/generate') && r.request().method() === 'POST',
      );
      await fenetre.getByRole('button', { name: /^générer$/i }).click();
      const reponseGeneration = await generation;
      if (reponseGeneration.status() === 201) {
        // Un bulletin a été validé et remis depuis : la lettre est produite.
        aSupprimer.push(((await reponseGeneration.json()) as { id: string }).id);
      } else {
        // Au 05/11/2026, tous les bulletins du test sont en brouillon.
        expect(reponseGeneration.status()).toBe(400);
        await expect(fenetre.getByRole('alert')).toContainText(/aucun bulletin remis à .+ : Martine n'atteste/i);
        await expect(fenetre).toBeVisible();
        await fenetre.getByRole('button', { name: /annuler/i }).click();
      }
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
    for (const id of aSupprimer) {
      const suppression = await page.request.delete(`${API_URL}/api/documents/${id}`, {
        headers: await enTetes(page),
      });
      expect(suppression.status(), `suppression de l'attestation ${id}`).toBe(204);
    }
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  }
});
