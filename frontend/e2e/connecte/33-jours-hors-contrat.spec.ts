import type { Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * L17-D (retour d'Elsa) : « griser le calendrier avant le début du contrat »
 * (salarié entré le 05/10 : les jours d'avant s'affichaient à saisir, avec une
 * alerte). Et L17-F : les jours payés par l'ancien logiciel (avant la bascule)
 * ne comptent plus dans « Reste à compléter », et l'écran le dit.
 *
 * Lecture seule : la garde vérifie qu'aucune écriture n'est partie.
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

test('jours avant l’entrée grisés « Hors contrat », non comptés à saisir', async ({ page }) => {
  test.setTimeout(240_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);

  await choisirSociete(page, /^lewis/i);
  // Un salarié présent entré en cours de mois, depuis juillet 2026.
  const salaries = (await (
    await page.request.get(`${API_URL}/api/employees`, { headers: await entetes(page) })
  ).json()) as {
    id: string;
    first_name: string;
    last_name: string;
    hire_date?: string | null;
    employment_status?: string | null;
  }[];
  const entre = salaries.find(
    (e) =>
      (e.employment_status ?? 'actif') !== 'parti' &&
      !!e.hire_date &&
      e.hire_date.slice(0, 10) >= '2026-07-02' &&
      e.hire_date.slice(0, 10) <= '2026-11-30' &&
      Number(e.hire_date.slice(8, 10)) > 1,
  );
  test.skip(!entre, 'aucun salarié entré en cours de mois depuis juillet dans la société de test');
  const embauche = entre!.hire_date!.slice(0, 10);
  const jourEntree = Number(embauche.slice(8, 10));

  await page.goto(`/schedules?month=${embauche.slice(0, 7)}`);
  const recherche = page.getByPlaceholder('Rechercher nom, prénom, poste…');
  await expect(recherche).toBeVisible({ timeout: 60_000 });
  await recherche.pressSequentially(entre!.last_name);

  // Première semaine du mois : les jours d'avant l'entrée sont « Hors contrat ».
  await page.getByRole('tab').first().click();
  const cases = page.getByTestId('case-hors-contrat').or(page.getByTestId('mention-hors-contrat'));
  await expect(cases.first()).toBeVisible({ timeout: 60_000 });
  await expect(cases.first()).toHaveText('Hors contrat');
  await expect(cases.first()).toHaveAttribute('title', /Avant l’entrée le \d{2}\/\d{2} : hors contrat, rien à saisir\./);

  // Calendrier du mois (tiroir) : autant de cases grises que de jours avant l'entrée.
  await page.getByRole('button', { name: 'Ouvrir le calendrier complet' }).first().click();
  const tiroir = page.getByRole('dialog');
  await expect(tiroir.getByTestId('entete-jours-du-mois')).toBeVisible({ timeout: 60_000 });
  // Grisés, ou visibles avec la mention « Hors contrat » s'ils portent une saisie.
  const grises = await tiroir.getByTestId('case-hors-contrat').count();
  const mentionnes = await tiroir.getByTestId('mention-hors-contrat').count();
  expect(grises + mentionnes).toBe(jourEntree - 1);
  // L'alerte du mois ne nomme aucun jour d'avant l'entrée.
  const alerte = tiroir.getByTestId('alerte-jours-a-saisir-tiroir');
  if (await alerte.isVisible()) {
    const mm = embauche.slice(5, 7);
    for (let j = 1; j < jourEntree; j++) {
      await expect(alerte).not.toContainText(`${String(j).padStart(2, '0')}/${mm} (`);
    }
  }
  await page.keyboard.press('Escape');
  await verifierPageSaine(page, s);
});

test('LEWIS, septembre 2026 : les jours payés par l’ancien logiciel ne sont pas comptés, et l’écran le dit', async ({ page }) => {
  test.setTimeout(240_000);
  await page.addInitScript(() => {
    if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
  });
  const s = surveiller(page);

  await choisirSociete(page, /^lewis/i);
  await page.goto('/schedules?month=2026-09');
  const phrase = page.getByTestId('jours-avant-bascule');
  await expect(phrase).toBeVisible({ timeout: 90_000 });
  await expect(phrase).toHaveText(/^Jours avant le \d{2}\/\d{2}\/2026 : payés par l’ancien logiciel( \(.+\))?, non comptés\.$/);
  await verifierPageSaine(page, s);
});
