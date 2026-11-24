import { test, expect } from '../helpers/garde';

// Connexion par lien, sans mot de passe.
// 1. La page de connexion propose « Recevoir un lien de connexion par e-mail » ; la
//    demande est interceptée (aucun e-mail ne part).
// 2. Avec E2E_LIEN_JETON (un lien d'invitation créé en base pour le compte QA, par le
//    script de création des liens, hors dépôt) : le lien ouvre la session,
//    puis le même lien est refusé avec un message clair.

test.use({ storageState: { cookies: [], origins: [] } });

test('la page de connexion propose un lien par e-mail', async ({ page }) => {
  let demande: unknown = null;
  await page.route('**/api/auth/lien-de-connexion', async (route) => {
    demande = route.request().postDataJSON();
    await route.fulfill({ json: { message: 'Si un compte existe pour cette adresse, un lien de connexion vient d’y être envoyé. Il est valable 30 minutes.' } });
  });
  await page.goto('/login');
  await page.getByRole('button', { name: /recevoir un lien de connexion par e-mail/i }).click();
  await page.locator('#lien-email').fill('quelqu.un@example.test');
  await page.getByRole('button', { name: /recevoir le lien/i }).click();
  await expect(page.getByText(/lien de connexion vient d.y être envoyé/i)).toBeVisible();
  expect(demande).toEqual({ email: 'quelqu.un@example.test' });
});

test('un lien ouvre la session une seule fois', async ({ page }) => {
  const jeton = process.env.E2E_LIEN_JETON;
  test.skip(!jeton, 'E2E_LIEN_JETON absent : lien d’invitation à créer en base');
  await page.goto(`/connexion?jeton=${jeton}`);
  await page.waitForURL((url) => !url.pathname.startsWith('/connexion') && !url.pathname.startsWith('/login'), {
    timeout: 30_000,
  });
  const jetonGarde = await page.evaluate(() => localStorage.getItem('authToken'));
  expect(jetonGarde, 'session ouverte').toBeTruthy();

  // Même lien, deuxième fois : refusé, et l'écran dit pourquoi.
  await page.evaluate(() => localStorage.clear());
  await page.goto(`/connexion?jeton=${jeton}`);
  await expect(page.getByRole('alert')).toContainText(/déjà servi ou il a expiré/i, { timeout: 30_000 });
});
