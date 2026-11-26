import { test, expect } from '../helpers/garde';
import { surveiller, verifierPageSaine } from '../helpers/erreurs';

/**
 * Retour d'Elsa du 26/11 : « il manque la possibilité de mettre un congé
 * parental ». Dans Nouveau congé, la RH choisit « Congé parental
 * d'éducation » et tape le premier jour et la fin prévue ; la demande part en
 * congé sans solde de sous-type conge_parental_education, par période.
 *
 * Aucune écriture : la création est simulée (route.fulfill) et son contenu
 * vérifié ; toute autre écriture serait bloquée par la garde.
 */
test.describe('Congé parental d’éducation', () => {
  test('se saisit du premier jour à la fin prévue, en sans solde de sous-type', async ({ page }) => {
    const s = surveiller(page);
    const envoyees: Record<string, unknown>[] = [];
    await page.route('**/api/absences/requests', async (route) => {
      const req = route.request();
      if (req.method() !== 'POST') return route.fallback();
      const corps = req.postDataJSON() as Record<string, unknown>;
      envoyees.push(corps);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'simule-conge-parental', status: 'validated', ...corps }),
      });
    });

    await page.goto('/leaves');
    await page.getByRole('button', { name: /Nouveau congé/ }).click();
    const fenetre = page.getByRole('dialog');
    await expect(fenetre.getByText('Nouveau congé', { exact: true })).toBeVisible({ timeout: 30_000 });

    await fenetre.locator('#absence-employee').click();
    await page.getByRole('option').first().click();

    await fenetre.locator('#absence-type').click();
    await page.getByRole('option', { name: "Congé parental d'éducation" }).click();

    const periode = fenetre.getByTestId('periode-conge-parental');
    await expect(periode).toBeVisible();
    await expect(periode.getByText(/suspension 632/)).toBeVisible();
    // Pas de calendrier jour par jour ni de demi-journée pour ce congé.
    await expect(fenetre.getByText('Jours demandés', { exact: true })).toHaveCount(0);

    // Sans fin prévue, la saisie est refusée avant tout envoi.
    // Champs de date natifs (aucune mise en forme de la frappe par Martine) :
    // l'ordre des segments au clavier dépend de la langue du navigateur de
    // test, pas de celle de l'utilisateur ; la valeur ISO se pose directement.
    await fenetre.locator('#conge-parental-debut').fill('2026-07-01');
    await fenetre.getByRole('button', { name: 'Enregistrer le congé' }).click();
    await expect(fenetre.getByText('Indiquez la fin prévue du congé parental.')).toBeVisible();
    expect(envoyees).toEqual([]);

    await fenetre.locator('#conge-parental-fin').fill('2027-06-30');
    await expect(fenetre.locator('#conge-parental-debut')).toHaveValue('2026-07-01');
    await expect(fenetre.locator('#conge-parental-fin')).toHaveValue('2027-06-30');
    await fenetre.getByRole('button', { name: 'Enregistrer le congé' }).click();

    await expect.poll(() => envoyees.length).toBe(1);
    expect(envoyees[0]).toMatchObject({
      type: 'sans_solde',
      event_subtype: 'conge_parental_education',
      date_debut: '2026-07-01',
      date_fin: '2027-06-30',
    });
    expect(envoyees[0]).not.toHaveProperty('selected_days');
    expect(envoyees[0]).not.toHaveProperty('demi_journees');
    expect(envoyees[0]).not.toHaveProperty('arret_type');
    await expect(fenetre).toBeHidden();

    await verifierPageSaine(page, s);
  });
});
