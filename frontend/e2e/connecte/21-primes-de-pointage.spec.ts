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

async function choisirType(page: Page, libelle: RegExp) {
  await page.getByText('Type de règle', { exact: true }).locator('..').getByRole('combobox').click();
  await page.getByRole('option', { name: libelle }).click();
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

  // Panier : postes de 4 h et de 12 h.
  await page.getByPlaceholder('Indemnité panier repas').fill('Panier équipe');
  await choisirType(page, /^Par jour travaillé/);
  const bloc = page.getByTestId('plages-debut');
  await bloc.getByRole('button', { name: /Ajouter une plage/ }).click();
  await bloc.getByLabel('Début de la plage 1').fill('03:00');
  await bloc.getByLabel('Fin de la plage 1').fill('05:00');
  await bloc.getByRole('button', { name: /Ajouter une plage/ }).click();
  await bloc.getByLabel('Début de la plage 2').fill('11:00');
  await bloc.getByLabel('Fin de la plage 2').fill('12:59');
  const perimetre = page.getByTestId('perimetre-pointage');
  await perimetre.getByRole('checkbox', { name: 'Hors forfait jours' }).click();
  await perimetre.getByRole('checkbox', { name: 'Hors cadres' }).click();
  await perimetre.getByRole('checkbox', { name: /Hors alternants/ }).click();
  await page.getByRole('button', { name: 'Ajouter la règle' }).click();
  await expect.poll(() => envoyees.length).toBe(1);
  expect(envoyees[0]).toMatchObject({
    rule_type: 'per_worked_day',
    conditions: {
      plages_debut: [
        { de: '03:00', a: '05:00' },
        { de: '11:00', a: '12:59' },
      ],
      exclure_forfait_jours: true,
      exclure_cadres: true,
      exclure_alternants: true,
      situation_repas: 'sur_lieu_travail',
    },
  });

  // Prime d'assiduité au mois, lue au calendrier.
  await page.getByPlaceholder('Indemnité panier repas').fill('Prime assiduité');
  await choisirType(page, /^Prime d’assiduité/);
  await page.getByTestId('reglage-assiduite').getByLabel('Versée').selectOption('mois');
  await expect(page.getByText('Montant mensuel à temps plein (€)')).toBeVisible();
  await page.getByRole('button', { name: 'Ajouter la règle' }).click();
  await expect.poll(() => envoyees.length).toBe(2);
  expect(envoyees[1]).toMatchObject({
    rule_type: 'per_week_without_absence',
    conditions: { periode_assiduite: 'mois' },
  });

  await verifierPageSaine(page, s);
});
