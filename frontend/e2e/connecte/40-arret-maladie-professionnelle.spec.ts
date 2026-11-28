import type { Locator, Page } from '@playwright/test';
import { test, expect } from '../helpers/garde';
import { erreursSerieuses, surveiller, verifierPageSaine } from '../helpers/erreurs';
import { API_URL } from '../helpers/env';

/**
 * L20 (capture du 27/11) : sous la nature « Arrêt maladie », la gestionnaire
 * choisit le type « Maladie professionnelle » ; l'enregistrement était refusé
 * (« ne correspond pas à la nature »). Désormais le type règle la nature, et la
 * fenêtre le dit ; une nature changée à la main retire un type qu'elle
 * n'accepte pas, et le dit aussi.
 *
 * Aucune écriture : la création est simulée (route.fulfill) et son contenu
 * vérifié ; toute autre écriture serait bloquée par la garde.
 */

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

type Envoi = Record<string, unknown>;

/** Simule POST /api/absences/requests : chaque corps envoyé est gardé. */
async function simulerCreation(page: Page, reponse: { status: number; json: unknown } | null) {
  const envois: Envoi[] = [];
  await page.route('**/api/absences/requests', async (route) => {
    const req = route.request();
    if (req.method() !== 'POST') return route.fallback();
    const corps = req.postDataJSON() as Envoi;
    envois.push(corps);
    await route.fulfill({
      status: reponse?.status ?? 201,
      contentType: 'application/json',
      body: JSON.stringify(reponse?.json ?? { id: 'simule-arret-mp', status: 'validated', ...corps }),
    });
  });
  return envois;
}

/** Le calendrier de la période affiche `mois` (index 0-11) de `annee`. */
async function afficherMois(page: Page, popover: Locator, mois: number, annee: number) {
  const cible = `${MOIS[mois]} ${annee}`;
  for (let i = 0; i < 36; i += 1) {
    if (await popover.getByRole('grid', { name: cible }).isVisible()) return;
    const premier = await popover
      .getByRole('grid')
      .first()
      .evaluate((g) => document.getElementById(g.getAttribute('aria-labelledby') ?? '')?.textContent ?? '');
    const [nom, an] = premier.trim().split(' ');
    const ecart = (annee - Number(an)) * 12 + (mois - MOIS.indexOf(nom));
    await popover.getByRole('button', { name: ecart > 0 ? 'Go to next month' : 'Go to previous month' }).click();
  }
  throw new Error(`le calendrier n'affiche pas ${cible}`);
}

/** Un jour du mois affiché (pas un jour d'un mois voisin grisé). */
function jour(popover: Locator, mois: number, annee: number, numero: number): Locator {
  return popover
    .getByRole('grid', { name: `${MOIS[mois]} ${annee}` })
    .getByRole('gridcell', { name: String(numero), exact: true })
    .and(popover.locator(':not(.day-outside)'));
}

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

test.describe('Arrêt en maladie professionnelle', () => {
  test('Arrêts & IJ : le type « Maladie professionnelle » règle la nature, l’arrêt part du premier coup', async ({
    page,
  }) => {
    test.setTimeout(180_000);
    const s = surveiller(page);
    const envois = await simulerCreation(page, null);

    await page.goto('/leaves');
    await page.getByTestId('renvoi-arrets').getByRole('link', { name: 'Arrêts & IJ' }).click();
    await expect(page.getByRole('heading', { name: 'Arrêts & IJ' })).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: /Enregistrer un arrêt/ }).click();
    const fenetre = page.getByRole('dialog', { name: 'Enregistrer un arrêt' });
    await expect(fenetre).toBeVisible();

    // Salarié : le premier de la liste, au clavier.
    await fenetre.locator('#absence-employee').click();
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    await expect(fenetre.locator('#absence-employee')).not.toContainText('Sélectionner un employé');

    // La nature proposée est « Arrêt maladie » ; on choisit le type
    // « Maladie professionnelle », comme sur la capture.
    await expect(fenetre.locator('#absence-type')).toContainText('Arrêt maladie');
    await fenetre.locator('#arret-type').click();
    await page.getByRole('option', { name: 'Maladie professionnelle', exact: true }).click();
    await expect(fenetre.locator('#arret-type')).toContainText('Maladie professionnelle');
    await expect(fenetre.locator('#absence-type')).toContainText('Maladie professionnelle');
    await expect(fenetre.getByTestId('nature-reglee')).toHaveText(
      "Nature réglée sur « Maladie professionnelle », qui va avec ce type d'arrêt.",
    );
    const dateAccident = fenetre.getByLabel("Date de l'accident ou de la première constatation");
    await expect(dateAccident).toHaveValue('');

    // Détour par l'accident du travail avec une date : revenir à la maladie
    // professionnelle par le type vide cette date, et la fenêtre le dit.
    await fenetre.locator('#arret-type').click();
    await page.getByRole('option', { name: 'Accident du travail', exact: true }).click();
    await expect(fenetre.locator('#absence-type')).toContainText('Accident du travail');
    // Champ de date natif : la valeur ISO se pose directement (cf. spec 27).
    await dateAccident.fill('2026-08-20');
    await fenetre.locator('#arret-type').click();
    await page.getByRole('option', { name: 'Maladie professionnelle', exact: true }).click();
    await expect(fenetre.getByTestId('nature-reglee')).toHaveText(
      "Nature réglée sur « Maladie professionnelle », qui va avec ce type d'arrêt. " +
        "La date saisie est vidée : indiquez celle de la première constatation, si vous l'avez.",
    );
    // La date de première constatation reste vide, comme sur la capture.
    await expect(dateAccident).toHaveValue('');
    await expect(fenetre.getByText(/Règle de la société/)).toBeVisible();

    // Période du 01/09/2026 au 29/11/2026.
    await fenetre.getByRole('button', { name: 'Cliquez pour choisir la période' }).click();
    const calendrier = page.locator('[data-radix-popper-content-wrapper]').last();
    await afficherMois(page, calendrier, 8, 2026);
    await jour(calendrier, 8, 2026, 1).click();
    await afficherMois(page, calendrier, 10, 2026);
    await jour(calendrier, 10, 2026, 29).click();
    await page.keyboard.press('Escape');
    await expect(fenetre.getByRole('button', { name: /^Du 01\/09\/2026 au 29\/11\/2026/ })).toBeVisible();

    await fenetre.getByRole('button', { name: "Enregistrer l'arrêt" }).click();
    const confirmation = page.getByTestId('confirmation-arret');
    await expect(confirmation).toContainText('Maladie professionnelle — Maladie professionnelle');
    expect(envois).toEqual([]);
    await confirmation.getByRole('button', { name: "Enregistrer l'arrêt" }).click();

    await expect.poll(() => envois.length).toBe(1);
    expect(envois[0]).toMatchObject({
      type: 'arret_maladie_pro',
      arret_type: 'maladie_professionnelle',
      date_debut: '2026-09-01',
      date_fin: '2026-11-29',
    });
    // Date vide : Martine prend le premier jour ; « règle de la société » :
    // la subrogation n'est pas envoyée, le serveur applique le réglage.
    expect(envois[0]).not.toHaveProperty('date_accident');
    expect(envois[0]).not.toHaveProperty('subrogation_active');
    await expect(fenetre).toBeHidden();
    await expect(page.getByText(/ne correspond pas à la nature/)).toHaveCount(0);

    await verifierPageSaine(page, s);
  });

  test('calendrier : la nature changée à la main retire le type, et un arrêt existant dit comment requalifier', async ({
    page,
  }) => {
    test.setTimeout(240_000);
    await page.addInitScript(() => {
      if (window.top === window) localStorage.removeItem('martine-rq-cache-v2');
    });
    const s = surveiller(page);
    const REFUS =
      'Ce salarié a déjà un arrêt enregistré du 01/09/2026 au 29/11/2026 (Arrêt maladie), qui recouvre la ' +
      'période saisie. Pour le requalifier en « Maladie professionnelle », ouvrez-le dans Arrêts & IJ, ' +
      'annulez-le (« Annuler cet arrêt »), puis saisissez de nouveau la période avec cette nature. Les ' +
      'bulletins déjà faits sur ces mois changent quand vous les recalculez.';
    const envois = await simulerCreation(page, { status: 400, json: { detail: REFUS } });

    await choisirSociete(page, /mont[\s-]?blanc/i);
    await page.goto('/schedules');
    const case_ = page.getByRole('button', { name: /^Éditer le \d+ pour / }).first();
    await expect(case_).toBeVisible({ timeout: 60_000 });
    await case_.click();
    await page.getByRole('button', { name: 'Signaler un arrêt à partir de ce jour' }).click();

    const fenetre = page.getByRole('dialog', { name: 'Enregistrer un arrêt' });
    await expect(fenetre).toBeVisible();
    await expect(fenetre.locator('#absence-type')).toContainText('Arrêt maladie');

    await fenetre.locator('#arret-type').click();
    await page.getByRole('option', { name: 'Maladie professionnelle', exact: true }).click();
    await expect(fenetre.getByTestId('nature-reglee')).toContainText('« Maladie professionnelle »');

    // Nature remise à « Arrêt maladie » à la main : le type ne va plus, il est
    // retiré et la fenêtre le dit (jamais un type affiché que la nature refuse).
    await fenetre.locator('#absence-type').click();
    await page.getByRole('option', { name: 'Arrêt maladie', exact: true }).click();
    await expect(fenetre.locator('#arret-type')).toContainText(/Sélectionner le type d.arrêt/);
    await expect(fenetre.getByTestId('type-arret-retire')).toHaveText(
      "Le type « Maladie professionnelle » ne va pas avec la nature « Arrêt maladie » : choisissez le type d'arrêt.",
    );

    // De nouveau le type : la nature suit.
    await fenetre.locator('#arret-type').click();
    await page.getByRole('option', { name: 'Maladie professionnelle', exact: true }).click();
    await expect(fenetre.locator('#absence-type')).toContainText('Maladie professionnelle');
    await expect(fenetre.getByTestId('type-arret-retire')).toHaveCount(0);

    await fenetre.getByRole('button', { name: "Enregistrer l'arrêt" }).click();
    const confirmation = page.getByTestId('confirmation-arret');
    await expect(confirmation).toContainText('Maladie professionnelle — Maladie professionnelle');
    await confirmation.getByRole('button', { name: "Enregistrer l'arrêt" }).click();

    await expect.poll(() => envois.length).toBe(1);
    expect(envois[0]).toMatchObject({ type: 'arret_maladie_pro', arret_type: 'maladie_professionnelle' });
    expect(envois[0].date_debut).toBe(envois[0].date_fin);

    // Le refus du serveur (arrêt maladie déjà enregistré) s'affiche dans la
    // fenêtre, restée ouverte, avec le chemin pour requalifier.
    await expect(fenetre).toBeVisible();
    await expect(fenetre.getByText(REFUS)).toBeVisible();

    await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
    await expect(page.getByText(/Une erreur s.est produite/)).toHaveCount(0);
    // Le 400 simulé est attendu ; toute autre erreur fait échouer le test.
    expect(erreursSerieuses(s).filter((e) => !/status of 400/.test(e))).toEqual([]);
  });
});
