import type { Page, Route } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

// Dispense de mutuelle (05/11/2026), sur l'écran d'une gestionnaire de paie
// (mode paie, comme 08-mode-paie). Rien n'est écrit : la fiche est relue telle
// quelle, sans mutuelle, et son enregistrement est intercepté. L'aperçu de la
// DSN, lui, est réel et ne fait que lire.

type Acces = Record<string, unknown> | null | undefined;
type Salarie = {
  id: string;
  employment_status?: string | null;
  statut?: string | null;
  contract_type?: string | null;
  missing_payroll_fields?: string[] | null;
  classification_conventionnelle?: Record<string, unknown> | null;
  specificites_paie?: Record<string, unknown> | null;
};

async function commeUneGestionnaireDePaie(page: Page) {
  await page.route('**/api/auth/me', async (route) => {
    const reponse = await route.fetch();
    const moi = await reponse.json();
    const enRh = (acces: Acces) => (acces ? { ...acces, role: 'rh' } : acces);
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

/** Coupée sans être retirée : voir 08-mode-paie (« route.fetch: Test ended »). */
async function intercepter(page: Page, url: string | RegExp, gerer: (route: Route) => Promise<void>) {
  let active = true;
  await page.route(url, (route) => (active ? gerer(route) : route.fallback()));
  return () => {
    active = false;
  };
}

async function entetes(page: Page) {
  const { jeton, societe } = await page.evaluate(() => ({
    jeton: localStorage.getItem('authToken'),
    societe: localStorage.getItem('activeCompanyId'),
  }));
  return { Authorization: `Bearer ${jeton}`, ...(societe ? { 'X-Active-Company': societe } : {}) };
}

async function lireApi<T>(page: Page, chemin: string): Promise<T> {
  const reponse = await page.request.get(`${API_URL}${chemin}`, { headers: await entetes(page) });
  expect(reponse.ok(), `lecture de ${chemin.split('?')[0]}`).toBeTruthy();
  return (await reponse.json()) as T;
}

test.use({ storageState: { cookies: [], origins: [] } });

async function seConnecter(page: Page) {
  await page.goto('/login');
  await page.locator('#login-username').fill(process.env.E2E_QA_EMAIL!);
  await page.locator('#login-password').fill(process.env.E2E_QA_PASSWORD!);
  await page.getByRole('button', { name: /se connecter/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 30_000 });
}

test('poser une dispense de mutuelle sur la fiche', async ({ page }) => {
  test.setTimeout(180_000);
  await commeUneGestionnaireDePaie(page);
  await page.addInitScript(() => localStorage.removeItem('martine-rq-cache-v2'));
  await seConnecter(page);
  await page.route('**/api/client-errors', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    await route.fulfill({ status: 204, body: '' });
  });
  const s = surveiller(page);

  const salaries = await lireApi<Salarie[]>(page, '/api/employees/summary?status=payroll');
  const cible = salaries.find(
    (e) =>
      ['actif', 'active', null, undefined].includes(e.employment_status) &&
      (e.statut ?? '').toLowerCase() !== 'cadre' &&
      (e.contract_type ?? '').toUpperCase() === 'CDI' &&
      !(e.missing_payroll_fields ?? []).length
  );
  expect(cible, 'un salarié non-cadre en CDI dans la société du compte QA').toBeTruthy();
  const lue = await lireApi<Salarie>(page, `/api/employees/${cible!.id}`);
  // Même garde que 08-mode-paie : un code PCS-ESE hors format bloquerait
  // l'enregistrement, ce test ne juge pas les données de la base partagée.
  const classification = lue.classification_conventionnelle;
  const propre =
    classification && typeof classification.pcs === 'string' && !/^\d{3}[a-z]$/.test(classification.pcs)
      ? { ...lue, classification_conventionnelle: { ...classification, pcs: '' } }
      : lue;
  const sansMutuelle: Salarie = {
    ...propre,
    specificites_paie: {
      ...(propre.specificites_paie ?? {}),
      mutuelle: { adhesion: false, mutuelle_type_ids: [], dispense: null },
    },
  };

  const envois: Array<Record<string, unknown>> = [];
  const couperFiche = await intercepter(page, new RegExp(`/api/employees/${cible!.id}(\\?.*)?$`), async (route) => {
    if (route.request().method() === 'PUT') {
      const corps = route.request().postDataJSON() as Record<string, unknown>;
      envois.push(corps);
      await route.fulfill({
        json: { ...sansMutuelle, specificites_paie: corps.specificites_paie ?? sansMutuelle.specificites_paie },
      });
      return;
    }
    if (route.request().method() !== 'GET') return route.fallback();
    await route.fulfill({ json: sansMutuelle });
  });

  await test.step('la dispense se pose dans Modifier la fiche', async () => {
    await page.goto(`/employees/${cible!.id}?modifier=fiche`);
    const fenetre = page.getByRole('dialog');
    await expect(fenetre).toBeVisible({ timeout: 30_000 });
    const caseDispense = fenetre.getByRole('checkbox', { name: /ne veut pas adhérer/i });
    await caseDispense.scrollIntoViewIfNeeded();
    await caseDispense.click();

    // Sans motif ni date : refusé, et l'écran dit quoi faire.
    await fenetre.getByRole('button', { name: /^enregistrer/i }).click();
    await expect(page.getByText(/Mutuelle : Choisissez le motif de la dispense/).first()).toBeVisible();
    expect(envois).toHaveLength(0);

    await fenetre.getByRole('combobox', { name: /motif de la dispense/i }).click();
    await page.getByRole('option', { name: /couvert ailleurs par une mutuelle collective/i }).click();
    await expect(fenetre.getByText(/D911-2 3°/)).toBeVisible();
    await fenetre.getByLabel(/demande signée reçue le/i).fill('2026-08-01');
    await expect(fenetre.getByLabel(/dernier justificatif reçu le/i)).toBeVisible();
    await fenetre.getByRole('button', { name: /^enregistrer/i }).click();
    await expect(fenetre).toHaveCount(0, { timeout: 30_000 });

    expect(envois).toHaveLength(1);
    const mutuelle = (envois[0].specificites_paie as Record<string, unknown>).mutuelle;
    expect(mutuelle).toMatchObject({
      adhesion: false,
      mutuelle_type_ids: [],
      dispense: {
        motif: 'couverture_collective',
        demande_recue_le: '2026-08-01',
        justificatif_recu_le: '2026-08-01',
        fin_le: null,
      },
    });
  });
  couperFiche();

  await test.step('l’alerte de la DSN dit quoi faire', async () => {
    // Aperçu réel (lecture seule) : l'ancienne phrase a disparu ; une mutuelle
    // absente dit désormais où poser la dispense.
    const reponse = await page.request.post(`${API_URL}/api/exports/preview`, {
      headers: await entetes(page),
      data: { export_type: 'dsn_mensuelle', period: '2026-08', filters: { dsn_type: 'dsn_mensuelle_normale' } },
    });
    expect(reponse.ok(), 'aperçu de la DSN d’août').toBeTruthy();
    const apercu = (await reponse.json()) as { warnings?: string[] };
    const alertes = apercu.warnings ?? [];
    expect(alertes.filter((w) => /alors que contrat actif/.test(w) && /mutuelle/.test(w))).toEqual([]);
    for (const w of alertes.filter((a) => /mutuelle absente/.test(a))) {
      expect(w).toMatch(/posez sa dispense/);
    }
  });

  await verifierPageSaine(page, s);
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});
