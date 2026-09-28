import { test, expect, type Page } from '@playwright/test';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

// L'écran d'une gestionnaire de paie cliente : rôle rh, pas administratrice
// plateforme, donc « mode paie » (navigation réduite, fiche allégée). Le compte
// QA est administrateur plateforme ; on le fait passer pour une gestionnaire en
// réécrivant la réponse de /api/auth/me. L'écran est le sien, le serveur garde
// les droits du compte QA. Rien n'est écrit : la seule écriture du parcours, la
// création d'un salarié, est interceptée.
//
// Un seul parcours, sur une seule page, comme une vraie session : l'application
// renouvelle sa session au retour sur la fenêtre, et des tests séparés repartant
// de la même session enregistrée se verraient refuser ce renouvellement.

type Acces = Record<string, unknown> | null | undefined;

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

/** Toute requête d'écriture vers l'API, hors renouvellement de session. */
function surveillerLesEcritures(page: Page) {
  const ecritures: string[] = [];
  page.on('request', (r) => {
    const url = new URL(r.url());
    if (!url.pathname.startsWith('/api/') || url.pathname.startsWith('/api/auth/')) return;
    if (!['GET', 'HEAD', 'OPTIONS'].includes(r.method())) ecritures.push(`${r.method()} ${url.pathname}`);
  });
  return ecritures;
}

type Salarie = {
  id: string;
  employment_status?: string | null;
  missing_payroll_fields?: string[] | null;
  statut?: string | null;
  contract_type?: string | null;
};

/** Lecture directe de l'API avec la session de la page. */
async function lireApi<T>(page: Page, chemin: string): Promise<T> {
  const { jeton, societe } = await page.evaluate(() => ({
    jeton: localStorage.getItem('authToken'),
    societe: localStorage.getItem('activeCompanyId'),
  }));
  const reponse = await page.request.get(`${API_URL}${chemin}`, {
    headers: { Authorization: `Bearer ${jeton}`, ...(societe ? { 'X-Active-Company': societe } : {}) },
  });
  expect(reponse.ok(), `lecture de ${chemin.split('?')[0]}`).toBeTruthy();
  return (await reponse.json()) as T;
}

test('le parcours d’une gestionnaire de paie', async ({ page }) => {
  test.setTimeout(240_000);
  await commeUneGestionnaireDePaie(page);
  // Chaque chargement repart sans le cache de requêtes que l'application garde
  // 24 h dans le navigateur : les réponses simulées sont bien celles affichées.
  await page.addInitScript(() => localStorage.removeItem('eywai-rq-cache-v1'));
  const s = surveiller(page);
  const ecritures = surveillerLesEcritures(page);

  await test.step('la navigation est réduite à la paie', async () => {
    await page.goto('/payroll');
    await expect(page.getByText(/gestion de la paie/i).first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/platforme admin/i)).toHaveCount(0);
    // Une page hors du périmètre paie renvoie au tableau de bord.
    await page.goto('/recruitment');
    await expect(page).toHaveURL((url) => url.pathname === '/', { timeout: 30_000 });
  });

  await test.step('créer un salarié depuis la page Paie', async () => {
    await page.route('**/api/employees', async (route) => {
      if (route.request().method() !== 'POST') return route.fallback();
      await route.fulfill({
        status: 201,
        json: {
          id: '00000000-0000-4000-8000-000000000081',
          username: 'jeanne.essai',
          first_name: 'Jeanne',
          last_name: 'Essai',
          generated_password: 'Provisoire-QA-8',
          a_completer: ['Numéro de sécurité sociale', 'Coordonnées bancaires (RIB)'],
          planning_mois: ['2026-10'],
          planning_plans: ['Plan QA'],
          acces_application: false,
        },
      });
    });
    await page.goto('/payroll');
    await expect(page.getByText(/gestion de la paie/i).first()).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: /nouveau collaborateur/i }).click();
    const fenetre = page.getByRole('dialog', { name: /nouveau collaborateur/i });
    await fenetre.getByLabel(/^prénom/i).fill('Jeanne');
    await fenetre.getByLabel(/^nom/i).fill('Essai');
    await fenetre.getByRole('tab', { name: 'Contrat' }).click();
    await fenetre.getByLabel(/date d'entrée/i).fill('2026-10-01');
    await fenetre.getByLabel(/intitulé du poste/i).fill('Opératrice QA');
    await fenetre.getByRole('tab', { name: 'Rémunération' }).click();
    await fenetre.getByLabel(/salaire de base mensuel/i).fill('1900');
    await fenetre.getByRole('button', { name: /enregistrer le collaborateur/i }).click();
    const recap = page.getByTestId('recap-nouveau-salarie');
    await expect(recap.getByText('Fiche créée : Jeanne Essai')).toBeVisible({ timeout: 30_000 });
    await expect(recap.getByText('Coordonnées bancaires (RIB)')).toBeVisible();
    await recap.getByRole('button', { name: 'Fermer' }).click();
    await page.unroute('**/api/employees');
  });

  const salaries = await test.step('lire la liste paie', () =>
    lireApi<Salarie[]>(page, '/api/employees/summary?status=payroll')
  );

  await test.step('une fiche à compléter se dit sur la paie et sur la fiche', async () => {
    // Comme une embauche du jour : non-cadre, en CDI, sans e-mail, fiche par
    // ailleurs complète.
    const cible = salaries.find(
      (e) =>
        ['actif', 'active', null, undefined].includes(e.employment_status) &&
        (e.statut ?? '').toLowerCase() !== 'cadre' &&
        (e.contract_type ?? '').toUpperCase() === 'CDI' &&
        !(e.missing_payroll_fields ?? []).length
    );
    expect(cible, 'un salarié non-cadre en CDI dans la société du compte QA').toBeTruthy();
    const manque = ['Numéro de sécurité sociale', 'Coordonnées bancaires (RIB)'];
    const aCompleter = <T extends Salarie>(e: T): T =>
      e.id === cible!.id
        ? {
            ...e,
            email: null,
            is_subject_to_residence_permit: false,
            employment_status: 'en_onboarding',
            missing_payroll_fields: manque,
            profile_complete: false,
            payroll_eligible: false,
          }
        : e;
    const resume = '**/api/employees/summary**';
    const fiche = new RegExp(`/api/employees/${cible!.id}(\\?.*)?$`);
    const ficheReelle = await lireApi<Salarie>(page, `/api/employees/${cible!.id}`);
    let completee = false;
    // La fiche du salarié, telle qu'une embauche du jour la laisserait ; une
    // fois « complétée », le serveur la rend telle qu'elle est.
    await page.route(resume, async (route) => {
      const reponse = await route.fetch();
      const liste = (await reponse.json()) as Salarie[];
      await route.fulfill({ response: reponse, json: completee ? liste : liste.map(aCompleter) });
    });
    await page.route(fiche, async (route) => {
      if (route.request().method() === 'PUT') {
        // Enregistrement intercepté : rien n'est écrit, la fiche réelle est rendue.
        completee = true;
      }
      await route.fulfill({ json: completee ? ficheReelle : aCompleter(ficheReelle) });
    });
    await page.goto(`/payroll?employee=${cible!.id}`);
    await expect(page.getByText(`Fiche à compléter : ${manque.join(', ')}`).first()).toBeVisible({
      timeout: 30_000,
    });
    await page.goto(`/employees/${cible!.id}`);
    await expect(page.getByText(/sa paie ne peut pas être générée tant que ces informations manquent/i)).toBeVisible({
      timeout: 30_000,
    });
    // La fenêtre de complément s'ouvre parfois d'elle-même (une fois par
    // session, selon le chargement de la fiche) ; le bouton, lui, est toujours là.
    const complement = page.getByRole('dialog');
    if (!(await complement.isVisible())) {
      await page.getByRole('button', { name: /compléter la fiche/i }).click();
    }
    await expect(complement.getByText(/sécurité sociale/i).first()).toBeVisible();
    await complement.getByRole('button', { name: /enregistrer/i }).click();
    await expect(complement).toHaveCount(0);
    // Retour à la paie par le menu, sans recharger : la fiche n'y bloque plus.
    const lienPaie = page.getByRole('link', { name: 'Bulletins de paie' });
    if (!(await lienPaie.isVisible())) await page.getByRole('button', { name: /EYWAI Paie/ }).click();
    await lienPaie.click();
    await expect(page.getByText(/gestion de la paie/i).first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/Fiche à compléter/)).toHaveCount(0, { timeout: 30_000 });
    await page.unroute(resume);
    await page.unroute(fiche);
  });

  await test.step('d’un salarié parti à ses documents de sortie', async () => {
    const parti = salaries.find((e) => e.employment_status === 'parti');
    expect(parti, 'un salarié parti dans la société du compte QA').toBeTruthy();
    await page.goto(`/employees/${parti!.id}`);
    const bandeau = page.getByTestId('dossier-de-depart');
    await expect(bandeau).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await bandeau.getByRole('link', { name: /ouvrir le dossier de départ/i }).click();
    await expect(page).toHaveURL(/\/employee-exits\?exitId=/);
    const dossier = page.getByRole('dialog');
    await expect(dossier).toBeVisible({ timeout: 30_000 });
    await dossier.getByRole('tab', { name: /documents/i }).click();
    await dossier.getByRole('button', { name: /générer un document/i }).click();
    for (const document of [/certificat de travail/i, /attestation employeur/i, /solde de tout compte/i]) {
      await expect(page.getByRole('menuitem', { name: document })).toBeVisible();
    }
    await page.keyboard.press('Escape');
  });

  // Seules écritures du parcours, interceptées : la création et la fiche complétée.
  expect(ecritures).toEqual(['POST /api/employees', expect.stringMatching(/^PUT \/api\/employees\/[0-9a-f-]+$/)]);
  await verifierPageSaine(page, s);
});
