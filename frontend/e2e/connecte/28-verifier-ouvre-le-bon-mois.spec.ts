import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * Retour du 26/11 (LEWIS) : sur « Générer la Paie » d'octobre, les anomalies
 * parlaient d'une « fenêtre des variables » et « Vérifier » ouvrait le
 * calendrier sur le mois en cours (novembre). La phrase nomme la paie du mois
 * et le lien ouvre le mois du premier jour à compléter. Lecture seule.
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

test('générer la paie d’octobre : la phrase nomme le mois, « Vérifier » ouvre le bon mois', async ({ page }) => {
  test.setTimeout(240_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);
  await choisirSociete(page, /^lewis/i);
  await page.goto('/payroll/generate');
  const fenetre = page.getByRole('dialog').first();
  await page.locator('#month-select').click({ timeout: 45_000 });
  await page.getByRole('option', { name: /octobre 2026/i }).click();

  const bandeau = fenetre.getByText(/anomalies? détectées?/).first();
  await expect(bandeau).toBeVisible({ timeout: 90_000 });
  await bandeau.click();
  await expect(fenetre.getByText('fenêtre des variables (')).toHaveCount(0);
  const phrase = fenetre.getByText(/à compléter pour la paie d’octobre|à compléter pour la paie d'octobre/).first();
  const aCompleter = await phrase
    .waitFor({ state: 'visible', timeout: 15_000 })
    .then(() => true)
    .catch(() => false);

  if (aCompleter) {
    // Le jour à compléter le plus tôt de cette anomalie donne le mois attendu.
    const texte = await phrase.innerText();
    const [, , mm] = texte.match(/: (\d{2})\/(\d{2})/) ?? [];
    expect(mm, 'un jour à compléter dans la phrase').toBeTruthy();
    const carte = phrase.locator('xpath=ancestor::*[.//button[normalize-space()="Vérifier"]][1]');
    await carte.getByRole('button', { name: 'Vérifier', exact: true }).first().click();
    await expect(page).toHaveURL(new RegExp(`tab=calendrier&year=2026&month=${Number(mm)}(&|$)`), {
      timeout: 30_000,
    });
  } else {
    // Calendriers d'octobre tous remplis (cas depuis le 27/11) : n'importe quelle
    // anomalie ouvre un mois de la fenêtre d'octobre (21/09 → 25/10), jamais novembre.
    await fenetre.getByRole('button', { name: 'Vérifier', exact: true }).first().click();
    await expect(page).toHaveURL(/tab=calendrier&year=2026&month=(9|10)(&|$)/, { timeout: 30_000 });
  }
  await verifierPageSaine(page, s);
});
