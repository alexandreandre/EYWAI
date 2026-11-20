import type { Page, Route } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * Retour d'Elsa du 17/11 : paniers et primes d'équipe liés aux pointages.
 * Chez Mont Blanc, on prépare dans Variables de paie :
 * - un panier « par jour travaillé » des postes qui commencent entre 3 h et
 *   5 h ou entre 11 h et 12 h 59, hors forfait jours, cadres et alternants ;
 * - une prime d'assiduité au mois.
 * L'ajout de la règle est simulé (rien n'est écrit) : on vérifie ce que
 * l'écran enverrait.
 */
async function entetes(page: Page) {
  const { jeton, societe } = await page.evaluate(() => ({
    jeton: localStorage.getItem('authToken'),
    societe: localStorage.getItem('activeCompanyId'),
  }));
  return { Authorization: `Bearer ${jeton}`, ...(societe ? { 'X-Active-Company': societe } : {}) };
}

async function choisirSociete(page: Page, nom: RegExp) {
  await page.goto('/');
  const societes = (await (
    await page.request.get(`${API_URL}/api/users/my-companies`, { headers: await entetes(page) })
  ).json()) as { company_id: string; company_name?: string }[];
  const soc = societes.find((c) => nom.test(c.company_name ?? ''));
  expect(soc, `la société ${nom} du compte QA`).toBeTruthy();
  await page.evaluate((id) => {
    localStorage.setItem('activeCompanyId', id);
    localStorage.removeItem('martine-rq-cache-v2');
  }, soc!.company_id);
}

async function ouvrirVariables(page: Page) {
  await page.goto('/company');
  await expect(page.getByText(/société|entreprise/i).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole('tab', { name: /paie/i }).first().click();
  await page.getByRole('button', { name: /^variables de paie/i }).first().click();
  await expect(page.getByText('Variables de paie récurrentes')).toBeVisible({ timeout: 20_000 });
}

test('panier et assiduité liés aux pointages, sans rien enregistrer', async ({ page }) => {
  test.setTimeout(180_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);
  const envoyees: Record<string, unknown>[] = [];
  await page.route('**/api/payroll-variables/rules', async (route: Route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    const corps = route.request().postDataJSON() as Record<string, unknown>;
    envoyees.push(corps);
    await route.fulfill({ status: 201, json: { id: 'simulee', company_id: 'x', ...corps } });
  });

  await choisirSociete(page, /mont[\s-]?blanc/i);
  await ouvrirVariables(page);

  // Réglage « préparer à chaque bulletin » visible dans la carte (on n'y touche pas : il écrit).
  await expect(page.getByTestId('preparation-auto')).toBeVisible();

  // Panier : parcours d'Elsa par le modèle, postes de 4 h et de 12 h tapés tels quels.
  await page.getByTestId('modeles-primes').getByRole('button', { name: /heure d’arrivée/ }).click();
  await page.getByPlaceholder('Indemnité panier repas').fill('Panier équipe');
  const perimetre = page.getByTestId('perimetre-pointage');
  await expect(perimetre.getByRole('checkbox', { name: 'Hors forfait jours' })).toBeChecked();
  await expect(perimetre.getByRole('checkbox', { name: 'Hors cadres' })).toBeChecked();
  await expect(perimetre.getByRole('checkbox', { name: /Hors alternants/ })).toBeChecked();
  const bloc = page.getByTestId('plages-debut');
  for (const heure of ['4', '12']) {
    await bloc.getByLabel('Heure du poste').fill(heure);
    await bloc.getByRole('button', { name: 'Ajouter ce poste' }).click();
  }
  await expect(bloc.getByText('Poste vers 4 h')).toBeVisible();
  await expect(bloc.getByText('Poste vers 12 h')).toBeVisible();
  // Montant oublié : refusé avec un message, rien n'est envoyé.
  await page.getByRole('button', { name: 'Ajouter la règle' }).click();
  await expect(page.getByText('Indiquez le montant de la prime.').first()).toBeVisible();
  expect(envoyees).toHaveLength(0);
  // Montant à virgule tapé au clavier (retour d'Elsa du 17/11 : impossible avant).
  const montant = page.getByText('Montant unitaire (€)', { exact: true }).locator('..').getByRole('textbox');
  await montant.pressSequentially('7,60');
  await expect(montant).toHaveValue('7,60');
  await page.getByRole('button', { name: 'Ajouter la règle' }).click();
  await expect.poll(() => envoyees.length).toBe(1);
  expect(envoyees[0]).toMatchObject({
    rule_type: 'per_worked_day',
    amount: 7.6,
    generation_mode: 'auto',
    conditions: {
      plages_debut: [
        { de: '03:00', a: '05:00' },
        { de: '11:00', a: '13:00' },
      ],
      exclure_forfait_jours: true,
      exclure_cadres: true,
      exclure_alternants: true,
      situation_repas: 'sur_lieu_travail',
    },
  });

  // Prime d'assiduité au mois, lue au calendrier, par le modèle.
  await page.getByTestId('modeles-primes').getByRole('button', { name: /assiduité/ }).click();
  await expect(page.getByText('Montant mensuel à temps plein (€)')).toBeVisible();
  const montantMois = page.getByText('Montant mensuel à temps plein (€)', { exact: true }).locator('..').getByRole('textbox');
  await montantMois.pressSequentially('50');
  await page.getByRole('button', { name: 'Ajouter la règle' }).click();
  await expect.poll(() => envoyees.length).toBe(2);
  expect(envoyees[1]).toMatchObject({
    rule_type: 'per_week_without_absence',
    amount: 50,
    conditions: { periode_assiduite: 'mois', exclure_cadres: true },
  });

  await verifierPageSaine(page, s);
});
