import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

/**
 * Retour d'Elsa (26/11) sur la liste de contrôle d'octobre : « 11 taux
 * périmés », « ça fait un peu peur le terme périmé », et elle veut voir la
 * liste. La ligne dit « à actualiser » et un dépliant nomme les salariés, avec
 * la date de leur taux et la fiche à ouvrir.
 * Lecture seule : la liste des taux est simulée dans le navigateur.
 */
test('la liste de contrôle nomme les taux d’impôt à actualiser, sans « périmé »', async ({ page }) => {
  test.setTimeout(120_000);
  const s = surveiller(page);
  await page.route('**/api/pas-rates', async (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    await route.fulfill({
      status: 200,
      json: {
        reference: '2026-11',
        compteurs: { a_jour: 1, a_rafraichir: 2 },
        lignes: [
          { employee_id: 'e2e-a', nom: 'Exemple', prenom: 'Alice', matricule: '', company_name: '', taux: 2.1, type_taux: '01', type_libelle: '', identifiant_taux: null, periode: '2026-10', source: 'dsn', statut: 'a_jour', statut_libelle: 'À jour' },
          { employee_id: 'e2e-b', nom: 'Exemple', prenom: 'Bruno', matricule: '', company_name: '', taux: 4.5, type_taux: '01', type_libelle: '', identifiant_taux: null, periode: '2026-07', source: 'dsn', statut: 'a_rafraichir', statut_libelle: 'À rafraîchir' },
          { employee_id: 'e2e-c', nom: 'Exemple', prenom: 'Chloé', matricule: '', company_name: '', taux: 0, type_taux: '01', type_libelle: '', identifiant_taux: null, periode: null, source: 'dsn', statut: 'a_rafraichir', statut_libelle: 'À rafraîchir' },
        ],
      },
    });
  });

  await page.goto('/payroll?view=month&month=2026-10');
  const liste = page.getByTestId('liste-controle-mois');
  await expect(liste.getByText('Taux d’impôt à jour')).toBeVisible({ timeout: 60_000 });
  await expect(liste.getByText(/2 taux à actualiser/)).toBeVisible();
  await expect(liste.getByText(/périm/i)).toHaveCount(0);

  await liste.getByText('Voir les 2 salariés concernés').click();
  const concernes = liste.getByTestId('salaries-concernes');
  await expect(concernes.getByText('Dernier taux reçu : juillet 2026 (plus de 2 mois)')).toBeVisible();
  await expect(concernes.getByText('Date du dernier taux inconnue')).toBeVisible();
  await expect(concernes.getByRole('link', { name: 'Bruno Exemple' })).toHaveAttribute('href', '/employees/e2e-b');
  await verifierPageSaine(page, s);
});
