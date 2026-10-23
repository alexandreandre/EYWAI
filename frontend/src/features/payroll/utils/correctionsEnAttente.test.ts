import { describe, expect, it } from 'vitest';

import { messageCorrectionsEnAttente } from './correctionsEnAttente';

/**
 * Jeu du 23/10 : la liste de contrôle disait « 1 bulletin a une correction en
 * attente », mais la ligne du salarié restait « Généré », sans un mot.
 */
describe('la ligne du mois dit la correction en attente', () => {
  it('rien en attente : rien à dire', () => {
    expect(messageCorrectionsEnAttente(undefined)).toBeNull();
    expect(messageCorrectionsEnAttente(0)).toBeNull();
  });

  it('dit quoi faire et où', () => {
    expect(messageCorrectionsEnAttente(1)).toBe(
      '1 correction ne trouve plus sa ligne : réglez-la dans l’onglet « Corriger » avant de valider.'
    );
    expect(messageCorrectionsEnAttente(2)).toBe(
      '2 corrections ne trouvent plus leur ligne : réglez-les dans l’onglet « Corriger » avant de valider.'
    );
  });
});
