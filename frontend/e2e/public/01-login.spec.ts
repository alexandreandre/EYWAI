import { test, expect } from '@playwright/test';
import { surveiller, erreursSerieuses } from '../helpers/erreurs';

test.describe('Page de connexion', () => {
  test('affiche le formulaire complet', async ({ page }) => {
    const s = surveiller(page);
    await page.goto('/login');
    await expect(page.locator('#login-username')).toBeVisible();
    await expect(page.locator('#login-password')).toBeVisible();
    await expect(page.getByRole('button', { name: /se connecter/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /mot de passe oublié/i })).toBeVisible();
    expect(erreursSerieuses(s)).toEqual([]);
  });

  test('refuse un mauvais mot de passe avec un message clair', async ({ page }) => {
    await page.goto('/login');
    await page.locator('#login-username').fill('qa.playwright@eywai.access.local');
    await page.locator('#login-password').fill('mauvais-mot-de-passe');
    await page.getByRole('button', { name: /se connecter/i }).click();
    await expect(page.getByText(/identifiant ou mot de passe incorrect/i)).toBeVisible();
    // On reste sur la page de login, sans jeton posé.
    expect(page.url()).toContain('/login');
    expect(await page.evaluate(() => window.localStorage.getItem('authToken'))).toBeNull();
  });

  test('une erreur distincte par cas : compte sans profil, serveur injoignable', async ({ page }) => {
    // Réponses simulées : rien n'atteint le serveur, rien n'est écrit.
    await page.route('**/api/client-errors', (route) => route.fulfill({ status: 204, body: '' }));
    await page.route('**/api/auth/logout', (route) => route.fulfill({ status: 204, body: '' }));
    await page.route('**/api/auth/me', (route) =>
      route.fulfill({ status: 404, json: { detail: 'Profil utilisateur non trouvé' } })
    );
    let coupure = false;
    await page.route('**/api/auth/login', (route) =>
      coupure
        ? route.abort('failed')
        : route.fulfill({
            json: { access_token: 'jeton-factice', refresh_token: 'factice', expires_in: 3600, expires_at: 0 },
          })
    );
    await page.goto('/login');
    await page.locator('#login-username').fill('qa.playwright@eywai.access.local');
    await page.locator('#login-password').fill('mot-de-passe-factice');
    await page.getByRole('button', { name: /se connecter/i }).click();
    // Le profil manque après l'authentification : la page ne se recharge pas, elle le dit.
    await expect(page.getByText(/pas encore ouvert dans Martine/i)).toBeVisible();
    expect(page.url()).toContain('/login');
    expect(await page.evaluate(() => window.localStorage.getItem('authToken'))).toBeNull();

    coupure = true;
    await page.getByRole('button', { name: /se connecter/i }).click();
    await expect(page.getByText(/ne répond pas.*mot de passe n’est pas en cause/i)).toBeVisible();
  });

  test('une route protégée sans session renvoie vers /login', async ({ page }) => {
    await page.goto('/employees');
    await page.waitForURL(/\/login/, { timeout: 30_000 });
    await expect(page.locator('#login-username')).toBeVisible();
  });
});
