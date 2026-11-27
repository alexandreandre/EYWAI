import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { erreursSerieuses, surveiller } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * L17-E (27/11) : « quand je rentre à la main 7 h, il faut pouvoir rentrer ses
 * horaires pour que ça déclenche un panier ». Dans l'éditeur d'un jour, l'heure
 * d'arrivée se tape au clavier ; sans heures faites elle est refusée avec la
 * raison ; avec, elle part dans l'enregistrement. L'enregistrement est simulé
 * (refusé par une réponse 409) : rien n'est écrit.
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

test('heure d’arrivée saisie à la main dans l’éditeur du jour', async ({ page }) => {
  test.setTimeout(240_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);

  const envois: string[] = [];
  await page.route(/\/api\/employees\/[^/]+\/calendar-save$/, async (route) => {
    envois.push(route.request().postData() ?? '');
    await route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Simulation du test : rien n’est enregistré.' }),
    });
  });

  await choisirSociete(page, /^lewis/i);
  await page.goto('/schedules');
  // Un jour « Travail » d'un salarié en heures.
  const jour = page
    .getByRole('button', { name: /^Éditer le \d+ pour / })
    .filter({ hasText: /^Travail/i })
    .first();
  await expect(jour).toBeVisible({ timeout: 60_000 });
  const numero = Number(((await jour.getAttribute('aria-label')) ?? '').match(/^Éditer le (\d+)/)?.[1]);
  await jour.click();

  const arrivee = page.getByLabel('Arrivée (facultatif)');
  await expect(arrivee).toBeVisible();
  const heuresFaites = page.getByLabel('H. faites');
  await heuresFaites.fill('');
  await arrivee.click();
  await page.keyboard.type('0700');
  await expect(arrivee).toHaveValue('07:00');

  // Sans heures faites : refusé, avec la raison, rien n'est parti.
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByTestId('erreur-editeur-jour')).toHaveText(
    'Saisissez les heures faites : l’heure d’arrivée n’est gardée que sur un jour travaillé.',
  );
  expect(envois).toHaveLength(0);

  // Avec 7 h faites, tapées au clavier : l'arrivée part avec le jour.
  await heuresFaites.click();
  await page.keyboard.type('7');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect.poll(() => envois.length).toBe(1);
  const corps = JSON.parse(envois[0]) as { calendrier_reel: { jour: number; debut?: string | null; heures_faites: number | null }[] };
  const envoye = corps.calendrier_reel.find((j) => j.jour === numero);
  expect(envoye).toMatchObject({ debut: '07:00', heures_faites: 7 });
  await expect(page.getByText('Enregistrement incomplet').first()).toBeVisible();
  // Le refus simulé de l'enregistrement est attendu ; rien d'autre ne doit casser.
  await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
  await expect(page.getByText(/Une erreur s.est produite/)).toHaveCount(0);
  expect(erreursSerieuses(s).filter((e) => !/calendar-save/.test(e))).toEqual([]);
});
