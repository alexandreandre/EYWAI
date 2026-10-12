import { describe, expect, it } from 'vitest';

import {
  avertissementMoisPrecedent,
  avertissementMoisPrecedentGroupe,
  moisPrecedentARecalculer,
} from './validationMoisPrecedent';

describe('valider un mois dont le mois précédent est à recalculer', () => {
  const lignes = [
    { year: 2026, month: 10, a_recalculer: false, status: 'brouillon' },
    { year: 2026, month: 9, a_recalculer: true, status: 'brouillon' },
  ];

  it('octobre : septembre est à recalculer', () => {
    expect(moisPrecedentARecalculer(lignes, 2026, 10)).toEqual({ year: 2026, month: 9 });
  });

  it('un septembre validé et changé depuis compte aussi', () => {
    const valide = [{ year: 2026, month: 9, a_recalculer: true, status: 'valide' }];
    expect(moisPrecedentARecalculer(valide, 2026, 10)).toEqual({ year: 2026, month: 9 });
  });

  it('rien à dire : à jour, inconnu, repris ou absent', () => {
    expect(moisPrecedentARecalculer([{ year: 2026, month: 9, a_recalculer: false }], 2026, 10)).toBeNull();
    expect(moisPrecedentARecalculer([{ year: 2026, month: 9, a_recalculer: null }], 2026, 10)).toBeNull();
    expect(
      moisPrecedentARecalculer([{ year: 2026, month: 9, a_recalculer: true, origine: 'importe' }], 2026, 10)
    ).toBeNull();
    expect(moisPrecedentARecalculer([], 2026, 10)).toBeNull();
  });

  it('janvier regarde décembre de l’année d’avant', () => {
    const decembre = [{ year: 2025, month: 12, a_recalculer: true }];
    expect(moisPrecedentARecalculer(decembre, 2026, 1)).toEqual({ year: 2025, month: 12 });
  });

  it('la phrase du bulletin, sans bloquer', () => {
    expect(avertissementMoisPrecedent({ year: 2026, month: 9 }, 2026, 10)).toBe(
      "Septembre 2026 est à recalculer : les cumuls d'octobre 2026 peuvent changer."
    );
    expect(avertissementMoisPrecedent({ year: 2026, month: 2 }, 2026, 3)).toBe(
      'Février 2026 est à recalculer : les cumuls de mars 2026 peuvent changer.'
    );
  });

  it('la phrase du groupe nomme les salariés, accordée', () => {
    expect(avertissementMoisPrecedentGroupe(['Mathis Exemple'], 2026, 10)).toBe(
      "Septembre 2026 est à recalculer pour Mathis Exemple : les cumuls de son bulletin d'octobre 2026 peuvent changer."
    );
    expect(avertissementMoisPrecedentGroupe(['A B', 'C D'], 2026, 10)).toBe(
      "Septembre 2026 est à recalculer pour 2 salariés (A B, C D) : les cumuls de leur bulletin d'octobre 2026 peuvent changer."
    );
    expect(avertissementMoisPrecedentGroupe([], 2026, 10)).toBeNull();
  });
});
