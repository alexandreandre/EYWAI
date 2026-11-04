import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

/**
 * Aperçu d'un signalement DSN avant envoi : la liste et l'aperçu sont
 * interceptés (données fictives), aucun fichier n'est généré. Le test échoue
 * si une génération (POST) part, même simulée.
 */
const SALARIE_ID = '00000000-0000-4000-8000-000000000101';
const NIR_FICTIF = '1850175123456';

const LISTE = {
  a_faire: [
    {
      employee_id: SALARIE_ID,
      salarie: 'DUPONT Jean',
      nature: '04',
      motif: '01',
      debut: '2026-10-05',
      fin_prevue: '2026-10-09',
      subrogation: false,
      connu_le: '2026-10-06',
      a_deposer_avant: '2026-10-11',
      date_reprise: null,
      en_retard: false,
      a_verifier: null,
    },
  ],
  faits: [],
};

const APERCU = {
  nature: '04',
  libelle_nature: "Signalement d'arrêt de travail",
  essai: false,
  nir_masque: true,
  blocs: [
    {
      code: 'S21.G00.06',
      libelle: 'Entreprise',
      partie: 'entreprise',
      rubriques: [{ code: 'S21.G00.06.001', libelle: 'SIREN', valeur: '000000000', traduction: null }],
    },
    {
      code: 'S21.G00.30',
      libelle: 'Individu',
      partie: 'salarie',
      rubriques: [
        { code: 'S21.G00.30.001', libelle: "Numéro d'inscription au répertoire", valeur: '18•••••••••56', traduction: null },
        { code: 'S21.G00.30.002', libelle: 'Nom de famille', valeur: 'DUPONT', traduction: null },
      ],
    },
    {
      code: 'S21.G00.60',
      libelle: 'Arrêt de travail',
      partie: 'evenement',
      rubriques: [
        { code: 'S21.G00.60.001', libelle: "Motif de l'arrêt", valeur: '01', traduction: 'maladie' },
        { code: 'S21.G00.60.003', libelle: 'Date de fin prévisionnelle', valeur: '09102026', traduction: null },
      ],
    },
  ],
  brut: [
    "S21.G00.06.001,'000000000'",
    "S21.G00.30.001,'18•••••••••56'",
    "S21.G00.30.002,'DUPONT'",
    "S21.G00.60.001,'01'",
    "S21.G00.60.003,'09102026'",
    '',
  ].join('\r\n'),
};

test("l'aperçu d'un signalement montre le fichier sans rien générer", async ({ page }) => {
  const s = surveiller(page);
  const generations: string[] = [];
  const apercus: string[] = [];

  await page.addInitScript(() => localStorage.removeItem('martine-rq-cache-v2'));
  await page.route('**/api/exports/dsn-signalements', async (route) => {
    if (route.request().method() === 'GET') return route.fulfill({ json: LISTE });
    // Une génération enregistrerait le fichier : elle ne doit jamais partir.
    generations.push(route.request().method());
    await route.fulfill({ status: 500, json: { detail: 'génération interdite dans ce test' } });
  });
  await page.route('**/api/exports/dsn-signalements/apercu**', async (route) => {
    if (route.request().method() !== 'GET') {
      generations.push(`${route.request().method()} apercu`);
      return route.fulfill({ status: 405, json: { detail: 'aperçu en lecture seule' } });
    }
    apercus.push(new URL(route.request().url()).searchParams.get('nature') ?? '');
    await route.fulfill({ json: APERCU });
  });

  await page.goto('/exports?tab=declarations');
  await expect(page).not.toHaveURL(/\/login/);
  await expect(page.getByText('Signalements DSN').first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('DUPONT Jean')).toBeVisible();

  // La ligne du salarié fictif : son nom, puis les boutons à côté.
  const ligne = page.getByText('DUPONT Jean').locator('xpath=../..');
  await ligne.getByRole('button', { name: 'Aperçu', exact: true }).click();
  const fenetre = page.getByRole('dialog');
  await expect(fenetre.getByText('Aperçu du signalement')).toBeVisible();
  await expect(fenetre.getByText(/Ce fichier n'est pas encore envoyé/)).toBeVisible();
  await expect(fenetre.getByRole('heading', { name: 'Salarié' })).toBeVisible();
  await expect(fenetre.getByText("Motif de l'arrêt")).toBeVisible();
  await expect(fenetre.getByText('maladie', { exact: true })).toBeVisible();
  await expect(fenetre.getByText('18•••••••••56')).toBeVisible();
  await expect(fenetre).not.toContainText(NIR_FICTIF);

  await fenetre.getByRole('tab', { name: 'Fichier brut' }).click();
  await expect(fenetre.getByTestId('apercu-brut')).toContainText("S21.G00.60.001,'01'");
  await expect(fenetre.getByText(/Seul le NIR est masqué/)).toBeVisible();

  await fenetre.getByRole('button', { name: 'Valider le format' }).click();
  await expect(page.getByRole('dialog')).toBeHidden();

  expect(apercus.length, 'l’aperçu a été demandé').toBeGreaterThan(0);
  expect(apercus.every((nature) => nature === '04')).toBe(true);
  expect(generations, 'aucune génération ne doit partir depuis l’aperçu').toEqual([]);
  await verifierPageSaine(page, s);
});
