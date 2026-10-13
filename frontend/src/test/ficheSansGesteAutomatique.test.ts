import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = path.resolve(__dirname, '..');
const lire = (rel: string) => readFileSync(path.join(SRC, rel), 'utf8').replace(/\s+/g, ' ');

/**
 * Rejeu final I.2 (13/10) : la fiche d'un salarié sans RIB ouvrait d'elle-même la
 * fenêtre « Finaliser l'onboarding », et l'enregistrer disait « Fiche complétée ».
 * Une fiche ne finalise rien toute seule : seul un geste de la gestionnaire
 * (« Compléter la fiche », « Modifier la fiche ») ouvre la fenêtre.
 */
describe('Fiche à compléter : la fenêtre ne s’ouvre que sur un geste', () => {
  const bandeau = lire('features/employee-detail/components/EmployeeOnboardingCompletion.tsx');

  it('le bandeau n’ouvre pas la fenêtre à l’arrivée sur la fiche', () => {
    expect(bandeau).not.toContain('useEffect');
    expect(bandeau).not.toContain('sessionStorage');
  });

  it('le bouton « Compléter la fiche » l’ouvre', () => {
    expect(bandeau).toContain('onClick={onOpenEdit}');
    expect(bandeau).toContain('Compléter la fiche');
  });
});
