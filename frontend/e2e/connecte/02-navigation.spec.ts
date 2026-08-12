import { test, expect } from '@playwright/test';
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

test('le bandeau ENVIRONNEMENT DE TEST est visible une fois connecté', async ({ page }) => {
  await page.goto('/');
  // Garde-fou : sans ce bandeau, on n'est PAS sur l'environnement de test.
  await expect(page.getByText('ENVIRONNEMENT DE TEST')).toBeVisible();
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
