import { defineConfig, devices } from '@playwright/test';
import { BASE_URL, ETAT_AUTH, identifiantsPresents } from './e2e/helpers/env';

/**
 * Config E2E EYWAI — cible par défaut : l'ENVIRONNEMENT DE TEST (Cloud Run).
 *
 * Identifiants et surcharges dans frontend/.env.e2e (gitignoré, voir
 * .env.e2e.example). La garde anti-prod (allowlist d'hôtes) vit dans
 * e2e/helpers/env.ts et s'applique dès le chargement de ce fichier.
 */

if (!identifiantsPresents) {
  console.warn(
    '[e2e] E2E_QA_EMAIL / E2E_QA_PASSWORD absents : seuls les tests publics tourneront. ' +
      'Renseigne frontend/.env.e2e (voir docs/qa/strategie-qa.md).',
  );
}

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  fullyParallel: false, // env de test partagé (Elsa peut y être) : une seule session à la fois
  workers: 1,
  retries: process.env.CI ? 2 : 1, // Cloud Run à froid : premières requêtes lentes
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: BASE_URL,
    locale: 'fr-FR',
    timezoneId: 'Europe/Paris',
    navigationTimeout: 45_000,
    actionTimeout: 20_000,
    // PLAYWRIGHT_NO_MEDIA (CI, dépôt public) : aucune capture — les données
    // affichées sont réelles et ne doivent jamais finir dans un artefact.
    trace: process.env.PLAYWRIGHT_NO_MEDIA ? 'off' : 'retain-on-failure',
    screenshot: process.env.PLAYWRIGHT_NO_MEDIA ? 'off' : 'only-on-failure',
    video: process.env.PLAYWRIGHT_NO_MEDIA ? 'off' : 'retain-on-failure',
  },
  projects: [
    {
      name: 'public',
      testMatch: /public\/.*\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
    ...(identifiantsPresents
      ? [
          {
            name: 'setup',
            testMatch: /auth\.setup\.ts/,
            use: { ...devices['Desktop Chrome'] },
          },
          {
            name: 'connecte',
            testMatch: /connecte\/.*\.spec\.ts/,
            dependencies: ['setup'],
            use: { ...devices['Desktop Chrome'], storageState: ETAT_AUTH },
          },
        ]
      : []),
  ],
});
