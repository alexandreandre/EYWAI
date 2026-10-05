import { describe, expect, it } from 'vitest';

import {
  dateEffetParDefaut,
  erreursChangementSalaire,
  messageSalaireEnregistre,
  salaireApplique,
  salaireVerrouille,
} from './salaireDate';

describe('salaireVerrouille', () => {
  it('verrouille le salaire de la fiche dès qu’un historique existe', () => {
    expect(
      salaireVerrouille([
        {
          id: 'h1',
          ancien_salaire: { valeur: 1900 },
          nouveau_salaire: { valeur: 2000 },
          effective_date: '2026-01-01',
          created_at: '2026-01-02T10:00:00Z',
        },
      ]),
    ).toBe(true);
  });

  it('laisse le salaire modifiable sans historique ou tant qu’il n’est pas lu', () => {
    expect(salaireVerrouille([])).toBe(false);
    expect(salaireVerrouille(undefined)).toBe(false);
  });
});

describe('dateEffetParDefaut', () => {
  it('propose le 1er du mois en cours', () => {
    expect(dateEffetParDefaut(new Date(2026, 9, 5))).toBe('2026-10-01');
    expect(dateEffetParDefaut(new Date(2027, 0, 31))).toBe('2027-01-01');
  });
});

describe('salaireApplique', () => {
  it('s’applique tout de suite jusqu’à aujourd’hui, plus tard après', () => {
    const aujourdhui = new Date(2026, 9, 5);
    expect(salaireApplique('2026-10-01', aujourdhui)).toBe(true);
    expect(salaireApplique('2026-10-05', aujourdhui)).toBe(true);
    expect(salaireApplique('2026-11-01', aujourdhui)).toBe(false);
  });
});

describe('erreursChangementSalaire', () => {
  it('exige un salaire positif et une date d’effet', () => {
    expect(erreursChangementSalaire({ montant: '', dateEffet: '2026-10-01' })).toEqual([
      'Saisissez le nouveau salaire de base mensuel brut.',
    ]);
    expect(erreursChangementSalaire({ montant: '0', dateEffet: '2026-10-01' })).toEqual([
      'Saisissez le nouveau salaire de base mensuel brut.',
    ]);
    expect(erreursChangementSalaire({ montant: '2100,50', dateEffet: '' })).toEqual([
      'Choisissez la date d’effet.',
    ]);
    expect(erreursChangementSalaire({ montant: '2100,50', dateEffet: '2026-10-01' })).toEqual([]);
  });
});

describe('messageSalaireEnregistre', () => {
  const aujourdhui = new Date(2026, 9, 5);

  it('dit ce qui change et ce qui passe à recalculer', () => {
    expect(messageSalaireEnregistre(2100.5, '2026-10-01', aujourdhui)).toBe(
      'Salaire de base : 2 100,50 € à compter du 01/10/2026. ' +
        'Les bulletins concernés passent « À recalculer ».',
    );
  });

  it('dit qu’une augmentation future ne change pas encore la fiche', () => {
    expect(messageSalaireEnregistre(2100, '2026-11-01', aujourdhui)).toBe(
      'Salaire de base : 2 100,00 € à compter du 01/11/2026. ' +
        'D’ici là, la fiche garde le salaire actuel.',
    );
  });
});
