import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * L17-A (retour d'Elsa) : « signaler un arrêt en cliquant sur le jour concerné ;
 * à l'étape de la saisie, double contrôle des dates ».
 *
 * Depuis la vue Planning : un jour, « Signaler un arrêt à partir de ce jour »,
 * la saisie d'Arrêts & IJ s'ouvre avec le salarié et le premier jour ; avant
 * d'enregistrer, la confirmation relit salarié, nature et période en toutes
 * lettres. On revient corriger : rien n'est enregistré (la garde le vérifie).
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

test('signaler un arrêt depuis un jour du planning, dates relues avant d’enregistrer', async ({ page }) => {
  test.setTimeout(240_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);

  await choisirSociete(page, /mont[\s-]?blanc/i);
  await page.goto('/schedules');

  // Un jour du planning de la semaine affichée.
  const jour = page.getByRole('button', { name: /^Éditer le \d+ pour / }).first();
  await expect(jour).toBeVisible({ timeout: 60_000 });
  const libelle = (await jour.getAttribute('aria-label')) ?? '';
  const [, numero, nom] = libelle.match(/^Éditer le (\d+) pour (.+)$/) ?? [];
  expect(numero, 'le numéro du jour').toBeTruthy();
  await jour.click();

  await page.getByRole('button', { name: 'Signaler un arrêt à partir de ce jour' }).click();

  const saisie = page.getByRole('dialog', { name: 'Enregistrer un arrêt' });
  await expect(saisie).toBeVisible();
  // Le premier jour est déjà choisi : il reste la fin (ici, un arrêt d'un jour).
  const jj = numero.padStart(2, '0');
  await expect(saisie.getByRole('button', { name: new RegExp(`^Du ${jj}/\\d{2}/\\d{4} au …$`) })).toBeVisible();

  // Nature de l'arrêt : un type proposé, choisi au clavier.
  await saisie.locator('#arret-type').click();
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  await expect(saisie.locator('#arret-type')).not.toContainText('Sélectionner le type');

  await saisie.getByRole('button', { name: "Enregistrer l'arrêt" }).click();

  // Double contrôle : salarié, nature, période en toutes lettres.
  const confirmation = page.getByTestId('confirmation-arret');
  await expect(confirmation).toBeVisible();
  await expect(confirmation).toContainText("Vérifiez l'arrêt avant de l'enregistrer");
  await expect(confirmation).toContainText(nom.split(' ')[0]);
  await expect(page.getByTestId('recapitulatif-periode-arret')).toHaveText(
    new RegExp(`^le [a-zé]+ ${jj}/\\d{2}/\\d{4} \\(1 jour calendaire\\)$`),
  );

  // On revient corriger : la saisie reste ouverte, rien n'est parti.
  await confirmation.getByRole('button', { name: 'Corriger les dates' }).click();
  await expect(confirmation).toBeHidden();
  await expect(saisie).toBeVisible();
  await saisie.getByRole('button', { name: 'Annuler', exact: true }).click();
  await expect(saisie).toBeHidden();
  await verifierPageSaine(page, s);
});
