import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

// Le code PCS-ESE : Martine le propose d'après le poste et le statut (route réelle
// /api/pcs-ese/proposition), la RH le voit et peut le changer. Rien n'est écrit : la fiche est
// relue puis son enregistrement intercepté ; la création est interceptée.
const VALEURS = {
  statut: 'Non-Cadre',
  contract_type: 'CDI',
  duree_hebdomadaire: 39,
  collective_agreement_id: null,
  classification_conventionnelle: null,
  mutuelle_type_ids_par_statut: { 'Non-Cadre': [], Cadre: [] },
  prevoyance_adhesion: true,
  titres_restaurant_beneficie: false,
};

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

type Salarie = {
  id: string;
  statut?: string | null;
  employment_status?: string | null;
  missing_payroll_fields?: string[] | null;
  classification_conventionnelle?: Record<string, unknown> | null;
};

test.describe('Code PCS-ESE proposé par Martine', () => {
  test('sur la fiche puis à la création : proposé avec sa raison, changeable, envoyé dans la classification', async ({ page }) => {
    const s = surveiller(page);

    await page.goto('/payroll');
    await expect(page.getByText(/gestion de la paie/i).first()).toBeVisible({ timeout: 30_000 });

    await test.step('sur la fiche d’un salarié à 9999', async () => {
      const salaries = await lireApi<Salarie[]>(page, '/api/employees/summary?status=payroll');
      const cible = salaries.find(
        (e) =>
          ['actif', 'active', null, undefined].includes(e.employment_status) &&
          (e.statut ?? '').toLowerCase() !== 'cadre' &&
          !(e.missing_payroll_fields ?? []).length,
      );
      expect(cible, 'un salarié non-cadre dans la société du compte QA').toBeTruthy();
      const lue = await lireApi<Salarie>(page, `/api/employees/${cible!.id}`);
      // La fiche réelle, relue avec ce poste et « 9999 » : le test ne dépend pas de la base.
      const fiche = {
        ...lue,
        job_title: 'Contrôleur de gestion',
        statut: 'Non-Cadre',
        classification_conventionnelle: { ...(lue.classification_conventionnelle ?? {}), pcs: '9999' },
      };
      const enregistre: Record<string, unknown>[] = [];
      const route = new RegExp(`/api/employees/${cible!.id}(\\?.*)?$`);
      await page.route(route, async (r) => {
        if (r.request().method() === 'PUT') {
          enregistre.push(r.request().postDataJSON() as Record<string, unknown>);
          await r.fulfill({ json: fiche });
          return;
        }
        if (r.request().method() !== 'GET') return r.fallback();
        await r.fulfill({ json: fiche });
      });

      await page.goto(`/employees/${cible!.id}?modifier=fiche`);
      const fenetre = page.getByRole('dialog');
      await expect(fenetre).toBeVisible({ timeout: 30_000 });
      const champ = fenetre.getByRole('combobox', { name: 'Code PCS-ESE' });
      await champ.scrollIntoViewIfNeeded();
      await expect(champ).toContainText('461d', { timeout: 30_000 });
      await expect(fenetre.getByText(/Proposé par Martine : Métier Insee/)).toBeVisible();

      // La RH change le code : le sien part, la mention de Martine disparaît.
      await champ.click();
      await page.getByPlaceholder(/code, intitulé ou métier/i).fill('674a');
      await page.getByRole('option', { name: /674a/ }).click();
      await expect(champ).toContainText('674a');
      await expect(fenetre.getByText(/Proposé par Martine/)).toHaveCount(0);

      await fenetre.getByRole('button', { name: /^enregistrer/i }).click();
      await expect(fenetre).toHaveCount(0, { timeout: 30_000 });
      expect(enregistre).toHaveLength(1);
      expect((enregistre[0].classification_conventionnelle as Record<string, unknown>).pcs).toBe('674a');
      await page.unroute(route);
    });

    await test.step('à la création', async () => {
    const envois: Record<string, unknown>[] = [];
    await page.route('**/api/employees/valeurs-embauche', (route) => route.fulfill({ json: VALEURS }));
    await page.route('**/api/collective-agreements/my-company', (route) => route.fulfill({ json: [] }));
    await page.route('**/api/employees', async (route) => {
      const request = route.request();
      if (request.method() !== 'POST') return route.fallback();
      const json = (request.postData() ?? '').match(/name="data"\r\n\r\n([\s\S]*?)\r\n--/);
      envois.push(json ? JSON.parse(json[1]) : {});
      // Réponse simulée : rien n'est créé dans la base partagée.
      await route.fulfill({
        status: 201,
        json: {
          id: '00000000-0000-4000-8000-000000000111',
          employee_folder_name: 'ESSAI_Jeanne',
          username: 'jeanne.essai',
          first_name: 'Jeanne',
          last_name: 'Essai',
          email: null,
          employment_status: 'en_onboarding',
          generated_password: 'Provisoire-QA-1',
          company_id: '00000000-0000-4000-8000-000000000112',
          warnings: [],
          a_completer: ['Numéro de sécurité sociale'],
          planning_mois: ['2026-09'],
          planning_plans: [],
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
    await fenetre.getByLabel(/date d'entrée/i).fill('2026-09-14');
    await fenetre.getByLabel(/intitulé du poste/i).fill('Contrôleur de gestion');

    const champ = fenetre.getByRole('combobox', { name: 'Code PCS-ESE' });
    await expect(champ).toContainText('461d', { timeout: 30_000 });
    await expect(fenetre.getByText(/Proposé par Martine : Métier Insee : « Contrôleur de gestion, non cadre »/)).toBeVisible();

    // L'onglet « Contrat » est démonté quand on le quitte : la proposition doit rester dite.
    await fenetre.getByRole('tab', { name: 'Rémunération' }).click();
    await fenetre.getByLabel(/salaire de base mensuel/i).fill('2400');
    await fenetre.getByRole('tab', { name: 'Contrat' }).click();
    await expect(champ).toContainText('461d');
    await expect(fenetre.getByText(/Proposé par Martine/)).toBeVisible();

    // La liste se cherche par métier.
    await champ.click();
    await page.getByPlaceholder(/code, intitulé ou métier/i).fill('soudeur');
    await expect(page.getByRole('option').first()).toBeVisible();
    await page.keyboard.press('Escape');

    await fenetre.getByRole('button', { name: /enregistrer le salarié|informations? à compléter/i }).click();
    await expect.poll(() => envois.length, { timeout: 15_000 }).toBe(1);
    expect(envois[0]).toMatchObject({
      job_title: 'Contrôleur de gestion',
      classification_conventionnelle: { pcs: '461d' },
    });
    expect(envois[0]).not.toHaveProperty('code_pcs');
    await expect(page.getByTestId('recap-nouveau-salarie').getByText('Fiche créée : Jeanne Essai')).toBeVisible();
    });
    await verifierPageSaine(page, s);
  });
});
