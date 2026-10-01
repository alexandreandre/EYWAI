import { describe, expect, it } from 'vitest';

import {
  TEXTE_PAS_DE_BULLETIN,
  messageComparaisonMoisDernier,
} from './comparaisonMoisDernier';

describe('messageComparaisonMoisDernier', () => {
  it('sans bulletin le mois dernier : la phrase, aucun chiffre inventé', () => {
    expect(messageComparaisonMoisDernier(null)).toBe(TEXTE_PAS_DE_BULLETIN);
    expect(messageComparaisonMoisDernier(undefined)).toBe(TEXTE_PAS_DE_BULLETIN);
    expect(messageComparaisonMoisDernier({ present: false, texte: TEXTE_PAS_DE_BULLETIN })).toBe(
      TEXTE_PAS_DE_BULLETIN
    );
    expect(messageComparaisonMoisDernier({ present: false, texte: TEXTE_PAS_DE_BULLETIN })).not.toMatch(
      /€|→|\d/
    );
  });

  it('affiche le texte déjà calculé, sans recalculer la paie', () => {
    const texte =
      'Brut : 2 000,00 € → 2 100,00 € · Net : 1 500,00 € → 1 600,00 € · Heures sup : 8 h → 12 h · Absences : 0 h → 14 h';
    expect(
      messageComparaisonMoisDernier({
        present: true,
        texte,
        brut: { avant: 2000, apres: 2100 },
      })
    ).toBe(texte);
  });

  it('un texte vide n’invente pas de montants', () => {
    expect(messageComparaisonMoisDernier({ present: true, texte: '  ' })).toBe(
      TEXTE_PAS_DE_BULLETIN
    );
  });
});
