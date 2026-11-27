import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * L17-B (retour d'Elsa) : « un gros bouton rouge pour annuler un modèle
 * appliqué par erreur, et pouvoir supprimer des lignes individuellement ».
 *
 * Page Plannings : un salarié coché, « Vider le calendrier du mois » ; la
 * confirmation dit, d'après l'aperçu du serveur (qui n'écrit rien), combien de
 * jours seront vidés et combien restent. On n'exécute pas : la garde bloque
 * toute écriture et vérifie qu'aucune n'est partie. Dans l'éditeur d'un jour,
 * « Vider ce jour » est proposé (ou refusé avec sa raison sur une absence).
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

test('vider le calendrier du mois : aperçu chiffré, rien d’écrit ; vider un jour proposé', async ({ page }) => {
  test.setTimeout(240_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);

  // Seule requête laissée passer : l'aperçu, qui n'écrit rien. Un vrai
  // vidage est bloqué ici et fait échouer le test.
  const apercus: string[] = [];
  const vidages: string[] = [];
  await page.route(/\/api\/employees\/[^/]+\/calendar\/vider-mois$/, async (route) => {
    const corps = route.request().postData() ?? '';
    if (JSON.parse(corps || '{}').apercu === true) {
      apercus.push(corps);
      await route.continue();
    } else {
      vidages.push(corps);
      await route.abort('blockedbyclient');
    }
  });

  await choisirSociete(page, /mont[\s-]?blanc/i);
  await page.goto('/schedules');

  // Un salarié coché, au clavier.
  const case1 = page.getByRole('checkbox', { name: /^Sélectionner / }).first();
  await expect(case1).toBeVisible({ timeout: 60_000 });
  await case1.focus();
  await page.keyboard.press('Space');

  const barre = page.getByRole('toolbar', { name: 'Saisie rapide' });
  await expect(barre).toContainText('1 sélectionné');
  await barre.getByRole('button', { name: 'Vider le calendrier du mois' }).click();

  const dialogue = page.getByTestId('dialogue-vider-calendrier');
  await expect(dialogue).toBeVisible();
  await expect(dialogue).toContainText(/Vider le calendrier de .+ — [a-zéû]+ \d{4}/);
  const bilan = page.getByTestId('bilan-vidage');
  await expect(bilan).toBeVisible({ timeout: 60_000 });
  await expect(bilan).toContainText(/\d+ jours? d[e’] ?.+ (seront vidés|sera vidé) \(prévu et réel\)|Rien à vider/);
  expect(apercus.length, 'une requête d’aperçu').toBe(1);
  expect(JSON.parse(apercus[0])).toMatchObject({ apercu: true });

  // On renonce : rien n'est vidé.
  await dialogue.getByRole('button', { name: /^(Annuler|Fermer)$/ }).click();
  await expect(dialogue).toBeHidden();
  await barre.getByRole('button', { name: 'Annuler', exact: true }).click();

  // « Vider ce jour » dans l'éditeur d'un jour.
  await page.getByRole('button', { name: /^Éditer le \d+ pour / }).first().click();
  const vider = page.getByRole('button', { name: 'Vider ce jour' });
  await expect(vider).toBeVisible();
  if (await vider.isDisabled()) {
    await expect(page.getByText('Absence posée : elle se retire dans Congés ou Arrêts & IJ')).toBeVisible();
  }
  await page.keyboard.press('Escape');
  expect(vidages, 'aucun vidage ne part').toEqual([]);
  await verifierPageSaine(page, s);
});
