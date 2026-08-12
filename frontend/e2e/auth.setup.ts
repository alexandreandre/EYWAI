import { test as setup, expect } from '@playwright/test';
import { ETAT_AUTH } from './helpers/env';

/**
 * Se connecte une fois via la vraie page de login (POST /api/auth/login) et
 * sauvegarde la session (localStorage : authToken / refreshToken) pour tous
 * les tests du projet « connecte ».
 */
setup('connexion du compte QA', async ({ page }) => {
  const email = process.env.E2E_QA_EMAIL!;
  const motDePasse = process.env.E2E_QA_PASSWORD!;

  await page.goto('/login');
  await expect(page.locator('#login-username')).toBeVisible();
  await page.locator('#login-username').fill(email);
  await page.locator('#login-password').fill(motDePasse);
  await page.getByRole('button', { name: /se connecter/i }).click();

  // Connexion réussie = on quitte /login et l'app pose son jeton.
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 30_000 });
  await expect
    .poll(async () => page.evaluate(() => window.localStorage.getItem('authToken')), {
      timeout: 15_000,
    })
    .not.toBeNull();

  await page.context().storageState({ path: ETAT_AUTH });
});
