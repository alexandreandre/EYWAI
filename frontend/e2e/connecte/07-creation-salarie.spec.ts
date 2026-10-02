import { test, expect, type Page } from '@playwright/test';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

// Parcours d'une gestionnaire de paie qui crée un salarié depuis la page Paie
// avec le seul minimum connu le jour de l'embauche. La création est
// interceptée : aucun salarié n'est créé dans la base partagée.
const SALARIE_ID = '00000000-0000-4000-8000-000000000071';

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

async function intercepterCreation(page: Page, valeurs: object = VALEURS) {
  const envois: Record<string, unknown>[] = [];
  await page.route('**/api/employees/valeurs-embauche', (route) => route.fulfill({ json: valeurs }));
  await page.route('**/api/employees', async (route) => {
    const request = route.request();
    if (request.method() !== 'POST') return route.fallback();
    const corps = request.postData() ?? '';
    const json = corps.match(/name="data"\r\n\r\n([\s\S]*?)\r\n--/);
    envois.push(json ? JSON.parse(json[1]) : {});
    await route.fulfill({
      status: 201,
      json: {
        id: SALARIE_ID,
        employee_folder_name: 'ESSAI_Jeanne',
        username: 'jeanne.essai',
        first_name: 'Jeanne',
        last_name: 'Essai',
        email: null,
        employment_status: 'en_onboarding',
        generated_password: 'Provisoire-QA-1',
        company_id: '00000000-0000-4000-8000-000000000072',
        warnings: [],
        a_completer: [
          'Numéro de sécurité sociale',
          'Date de naissance',
          'Adresse postale',
          'Coordonnées bancaires (RIB)',
        ],
        planning_mois: ['2026-09', '2026-10', '2026-11', '2026-12'],
        planning_plans: ['Plan QA — 2026'],
        acces_application: false,
      },
    });
  });
  return envois;
}

test.describe('Création d’un salarié depuis la paie', () => {
  test('le minimum suffit, les erreurs mènent au bon onglet, le récapitulatif dit ce qui reste', async ({ page }) => {
    const s = surveiller(page);
    const envois = await intercepterCreation(page);

    await page.goto('/payroll');
    await expect(page.getByText(/gestion de la paie/i).first()).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: /nouveau collaborateur/i }).click();

    const fenetre = page.getByRole('dialog', { name: /nouveau collaborateur/i });
    await expect(fenetre.getByText(/seuls le nom, le prénom, le poste/i)).toBeVisible();

    await fenetre.getByLabel(/^prénom/i).fill('Jeanne');
    await fenetre.getByLabel(/^nom/i).fill('Essai');
    await fenetre.getByRole('button', { name: /enregistrer le salarié|informations? à compléter/i }).click();

    // Date d'entrée et poste manquent : on est conduit à l'onglet Contrat.
    await expect(fenetre.getByText("Date d'entrée : Date d'entrée requise.")).toBeVisible();
    await expect(fenetre.getByText('Salaire de base : Salaire requis.')).toBeVisible();
    await expect(fenetre.getByRole('tab', { name: 'Contrat' })).toHaveAttribute('aria-selected', 'true');
    await expect(fenetre.getByLabel(/durée hebdo/i)).toHaveValue('39');

    await fenetre.getByLabel(/date d'entrée/i).fill('2026-09-14');
    await fenetre.getByLabel(/intitulé du poste/i).fill('Préparatrice QA');
    await fenetre.getByRole('button', { name: /enregistrer le salarié|informations? à compléter/i }).click();

    // Reste le salaire : onglet Rémunération.
    await expect(fenetre.getByRole('tab', { name: 'Rémunération' })).toHaveAttribute('aria-selected', 'true');
    await fenetre.getByLabel(/salaire de base mensuel/i).fill('1990');
    await fenetre.getByRole('button', { name: /enregistrer le salarié|informations? à compléter/i }).click();

    const recap = page.getByTestId('recap-nouveau-salarie');
    await expect(recap.getByText('Fiche créée : Jeanne Essai')).toBeVisible();
    await expect(recap.getByText(/de septembre à décembre 2026/)).toBeVisible();
    await expect(recap.getByText('Numéro de sécurité sociale')).toBeVisible();
    await expect(recap.getByText('Coordonnées bancaires (RIB)')).toBeVisible();
    await expect(recap.getByText('jeanne.essai')).toBeVisible();
    await expect(recap.getByText(/sans e-mail/i)).toBeVisible();

    expect(envois).toHaveLength(1);
    expect(envois[0]).toMatchObject({
      first_name: 'Jeanne',
      last_name: 'Essai',
      job_title: 'Préparatrice QA',
      hire_date: '2026-09-14',
      salaire_de_base: { valeur: 1990 },
      duree_hebdomadaire: 39,
      email: null,
      nir: null,
      date_naissance: null,
      adresse: null,
      coordonnees_bancaires: null,
    });

    await recap.getByRole('button', { name: 'Fermer' }).click();
    await expect(recap).toBeHidden();
    await verifierPageSaine(page, s);
  });

  test('la classification et la mutuelle habituelles de la société sont reprises', async ({ page }) => {
    // Grille de la convention sans la classification que portent les salariés
    // (cas réel : « C / 710 » contre « Non précisé / 700, 710, 720 »).
    const envois = await intercepterCreation(page, {
      ...VALEURS,
      collective_agreement_id: 'cc-qa',
      classification_conventionnelle: { groupe_emploi: 'C', classe_emploi: 710, coefficient: 710 },
      mutuelle_type_ids_par_statut: { 'Non-Cadre': ['mutuelle-non-cadre'], Cadre: ['mutuelle-cadre'] },
    });
    await page.route('**/api/collective-agreements/my-company', (route) =>
      route.fulfill({
        json: [
          {
            id: 'lien-qa',
            company_id: 'societe-qa',
            collective_agreement_id: 'cc-qa',
            assigned_at: '2026-01-01T00:00:00Z',
            agreement_details: { id: 'cc-qa', name: 'Convention QA', idcc: '9999', is_active: true },
          },
        ],
      })
    );
    await page.route('**/api/collective-agreements/catalog/cc-qa/classifications', (route) =>
      route.fulfill({
        json: [700, 710, 720].map((coefficient) => ({ groupe_emploi: 'Non précisé', classe_emploi: 0, coefficient })),
      })
    );

    await page.goto('/payroll');
    await expect(page.getByText(/gestion de la paie/i).first()).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: /nouveau collaborateur/i }).click();
    const fenetre = page.getByRole('dialog', { name: /nouveau collaborateur/i });
    await expect(fenetre.getByText(/reprennent celles de vos salariés/i)).toBeVisible();

    await fenetre.getByLabel(/^prénom/i).fill('Jeanne');
    await fenetre.getByLabel(/^nom/i).fill('Essai');
    await fenetre.getByRole('tab', { name: 'Contrat' }).click();
    await fenetre.getByLabel(/date d'entrée/i).fill('2026-09-14');
    await fenetre.getByLabel(/intitulé du poste/i).fill('Responsable QA');
    // Passage cadre : la mutuelle de la société suit la catégorie.
    await fenetre.getByRole('combobox').filter({ hasText: 'Non-Cadre' }).click();
    await page.getByRole('option', { name: 'Cadre', exact: true }).click();

    await fenetre.getByRole('tab', { name: 'Rémunération' }).click();
    await expect(fenetre.getByRole('combobox').filter({ hasText: 'Groupe C - Classe 710 - Coeff. 710' })).toBeVisible();
    await fenetre.getByLabel(/salaire de base mensuel/i).fill('3200');
    await fenetre.getByRole('button', { name: /enregistrer le salarié|informations? à compléter/i }).click();

    await expect(page.getByTestId('recap-nouveau-salarie')).toBeVisible();
    expect(envois[0]).toMatchObject({
      statut: 'Cadre',
      collective_agreement_id: 'cc-qa',
      classification_conventionnelle: { groupe_emploi: 'C', classe_emploi: 710, coefficient: 710 },
      specificites_paie: { mutuelle: { mutuelle_type_ids: ['mutuelle-cadre'] }, prevoyance: { adhesion: true } },
    });
  });
});
