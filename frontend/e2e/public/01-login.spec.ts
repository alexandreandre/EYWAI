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

  test('une route protégée sans session renvoie vers /login', async ({ page }) => {
    await page.goto('/employees');
    await page.waitForURL(/\/login/, { timeout: 30_000 });
    await expect(page.locator('#login-username')).toBeVisible();
  });
});
