import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * Activité partielle en masse (26/11, LEWIS : « tous les vendredis, tout le
 * monde est en activité partielle »). Depuis la page des plannings : la
 * fenêtre, une période tapée au clavier, le vendredi coché, la liste des dates
 * et l'aperçu calculé par le serveur, avec son décompte.
 *
 * Rien n'est enregistré : la garde bloque toute écriture, sauf la requête
 * d'aperçu, qui calcule sans rien écrire (laissée passer ci-dessous).
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

test('activité partielle en masse (LEWIS) : les vendredis d’une période, aperçu sans rien écrire', async ({ page }) => {
  test.setTimeout(240_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);

  // Seule écriture permise : l'aperçu, qui n'écrit rien. Enregistrée après la
  // garde, cette route passe avant elle ; l'enregistrement reste bloqué.
  const apercus: string[] = [];
  await page.route(/\/api\/schedules\/activite-partielle-en-masse\/apercu$/, async (route) => {
    apercus.push(route.request().postData() ?? '');
    await route.continue();
  });

  await choisirSociete(page, /^lewis/i);
  await page.goto('/schedules');
  const bouton = page.getByRole('button', { name: 'Activité partielle en masse' });
  await expect(bouton, 'LEWIS a l’activité partielle activée').toBeVisible({ timeout: 45_000 });
  await bouton.click();

  const fenetre = page.getByRole('dialog', { name: 'Activité partielle en masse' });
  await expect(fenetre).toBeVisible();
  const dates = fenetre.getByTestId('ap-masse-dates');
  await expect(dates).toContainText('Aucun jour retenu');
  await expect(fenetre.getByText('Choisissez des jours : l’aperçu dira combien')).toBeVisible();

  // Du 01/12/2026 au 31/12/2026, tapé au clavier (champ de date en français).
  const du = fenetre.getByLabel('Du', { exact: true });
  // Champ date natif : l'ordre jour/mois dépend de la langue du navigateur ; on donne la date ISO.
  await du.fill('2026-12-01');
  await expect(du).toHaveValue('2026-12-01');
  const au = fenetre.getByLabel('Au', { exact: true });
  await au.fill('2026-12-31');
  await expect(au).toHaveValue('2026-12-31');
  await expect(fenetre.getByText('Cochez les jours de la semaine à prendre sur cette période.')).toBeVisible();

  await fenetre.getByRole('checkbox', { name: 'vendredi', exact: true }).click();
  await expect(dates).toContainText('4 jours retenus');
  await expect(dates).toContainText('ven. 04/12/2026, ven. 11/12/2026, ven. 18/12/2026, ven. 25/12/2026');

  // Les salariés du mois, tous cochés par défaut.
  const nb = fenetre.getByTestId('ap-masse-nb-salaries');
  await expect(nb).toBeVisible({ timeout: 30_000 });
  const [, cochesTexte, totalTexte] = (await nb.innerText()).match(/(\d+) salariés? cochés? sur (\d+)/) ?? [];
  expect(Number(cochesTexte)).toBeGreaterThan(0);
  expect(cochesTexte).toBe(totalTexte);

  // L'aperçu du serveur : un décompte ; le 25/12 (Noël) reste tel quel pour tous.
  const decompte = fenetre.getByTestId('ap-masse-decompte');
  await expect(decompte).toBeVisible({ timeout: 90_000 });
  await expect(decompte).toContainText(/\d+ jours? (passeront|passera) en activité partielle|Rien à poser/);
  await expect(decompte).toContainText('Jours qui resteront tels quels');
  await expect(decompte).toContainText(/\d+ jours? : /);

  expect(apercus.length, 'une requête d’aperçu').toBeGreaterThan(0);
  const corps = JSON.parse(apercus[apercus.length - 1]) as { dates: string[]; employee_ids: string[] };
  expect(corps.dates).toEqual(['2026-12-04', '2026-12-11', '2026-12-18', '2026-12-25']);
  expect(corps.employee_ids).toHaveLength(Number(cochesTexte));

  // On ferme sans enregistrer : la garde vérifie qu'aucune écriture n'est partie.
  await fenetre.getByRole('button', { name: 'Fermer', exact: true }).click();
  await expect(fenetre).toBeHidden();
  await verifierPageSaine(page, s);
});
