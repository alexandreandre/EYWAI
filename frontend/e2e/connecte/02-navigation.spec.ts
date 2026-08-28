import { test, expect } from '@playwright/test';
import { API_URL } from '../helpers/env';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

/**
 * Balaye les pages RH critiques : chacune doit se rendre sans crash
 * (ErrorBoundary), sans renvoyer vers /login, et sans erreur console/5xx.
 * Volontairement tolérant aux états vides — le contenu métier est testé
 * dans les specs dédiées.
 */
const PAGES: Array<{ chemin: string; nom: string }> = [
  { chemin: '/', nom: 'Tableau de bord RH' },
  { chemin: '/employees', nom: 'Collaborateurs' },
  { chemin: '/payroll', nom: 'Paie' },
  { chemin: '/payroll/generate', nom: 'Génération de paie' },
  { chemin: '/leaves', nom: 'Congés & absences' },
  { chemin: '/exports', nom: 'Exports' },
  { chemin: '/badgeuse-rh', nom: 'Badgeuse RH' },
  { chemin: '/planning', nom: 'Planning' },
  { chemin: '/suivi-temps-travail', nom: 'Suivi du temps de travail' },
  { chemin: '/saisies', nom: 'Éléments variables (primes)' },
  { chemin: '/company', nom: 'Paramétrage société' },
  { chemin: '/users', nom: 'Utilisateurs' },
  { chemin: '/simulation', nom: 'Simulation de paie' },
  { chemin: '/documents', nom: 'Documents' },
  { chemin: '/trial-periods', nom: 'Périodes d’essai' },
];

test('l’API de resynchro reste disponible (bandeau retiré)', async ({ request }) => {
  const rep = await request.get(`${API_URL}/api/test-env/status`);
  expect(rep.status()).not.toBe(404);
});

for (const { chemin, nom } of PAGES) {
  test(`${nom} (${chemin}) se rend sans erreur`, async ({ page }) => {
    const s = surveiller(page);
    await page.goto(chemin);

    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.locator('#root > *:visible').first()).toBeVisible();
    await verifierPageSaine(page, s, `Erreurs sur ${chemin}`);
  });
}
