import { test, expect } from '../helpers/garde';

// Lien d'invitation : la personne crée son mot de passe, puis elle est connectée.
// Avec E2E_LIEN_JETON (un lien d'invitation créé en base pour le compte QA, par le
// script de création des liens, hors dépôt). Le « nouveau » mot de passe est celui
// du compte QA : le compte ne change pas pour les autres parcours.
//   1. Ouvrir le lien (et recharger la page) ne le consomme pas : formulaire affiché.
//   2. Un mot de passe trop faible est refusé, sans griller le lien.
//   3. Le mot de passe enregistré, la session s'ouvre.
//   4. Le même lien, rouvert, dit qu'il n'est plus valable.

test.use({ storageState: { cookies: [], origins: [] } });

test('le lien d’invitation fait créer le mot de passe, une seule fois', async ({ page }) => {
  const jeton = process.env.E2E_LIEN_JETON;
  test.skip(!jeton, 'E2E_LIEN_JETON absent : lien d’invitation à créer en base');
  const motDePasse = process.env.E2E_QA_PASSWORD!;

  await page.goto(`/connexion?jeton=${jeton}`);
  await expect(page.getByText(/créez votre mot de passe/i)).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('#invitation-email')).toHaveValue(process.env.E2E_QA_EMAIL!.toLowerCase());
  await page.reload();
  await expect(page.getByText(/créez votre mot de passe/i)).toBeVisible({ timeout: 30_000 });
  expect(await page.evaluate(() => localStorage.getItem('authToken'))).toBeFalsy();

  const bouton = page.getByRole('button', { name: /créer mon mot de passe et me connecter/i });
  await page.locator('#invitation-mot-de-passe').fill('court');
  await page.locator('#invitation-confirmation').fill('court');
  await expect(bouton).toBeDisabled();

  await page.locator('#invitation-mot-de-passe').fill(motDePasse);
  await page.locator('#invitation-confirmation').fill(motDePasse);
  await bouton.click();
  await page.waitForURL((url) => !url.pathname.startsWith('/connexion') && !url.pathname.startsWith('/login'), {
    timeout: 30_000,
  });
  expect(await page.evaluate(() => localStorage.getItem('authToken')), 'session ouverte').toBeTruthy();

  await page.evaluate(() => localStorage.clear());
  await page.goto(`/connexion?jeton=${jeton}`);
  await expect(page.getByRole('alert')).toContainText(/déjà servi ou il a expiré/i, { timeout: 30_000 });
});
