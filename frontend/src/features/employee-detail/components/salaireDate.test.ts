import { describe, expect, it } from 'vitest';

import {
  avertissementSalaireNonDate,
  dateEffetParDefaut,
  texteSalaireActuel,
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

/**
 * Salarié sans historique de salaire (vidéo G, 11/10/2026) : « Changer le
 * salaire » n'apparaissait pas, et changer le champ de la fiche remplaçait le
 * salaire sans date ni rappel, sans un mot. Le bouton est proposé aussi sans
 * historique (la première ligne part du salaire actuel) ; le champ direct dit
 * ce qu'il fait.
 */
describe('salaire sans historique', () => {
  it('le texte du bouton dit que le changement daté part du salaire actuel', () => {
    expect(texteSalaireActuel(2100, false)).toBe(
      'Salaire de base actuel : 2 100,00 €. Aucun historique de salaire : « Changer le salaire » ' +
        'en ouvre un à partir de ce salaire, avec une date d’effet et le rappel des mois déjà payés.',
    );
  });

  it('avec un historique, le texte reste celui de l’historique', () => {
    expect(texteSalaireActuel(2100, true)).toBe(
      'Salaire de base actuel : 2 100,00 €. Il suit l’historique des salaires : il se change avec une date d’effet.',
    );
  });

  it('un salaire inconnu ne s’écrit pas « NaN »', () => {
    expect(texteSalaireActuel(null, true)).toBe(
      'Salaire de base actuel : —. Il suit l’historique des salaires : il se change avec une date d’effet.',
    );
  });

  it('changé dans le champ de la fiche, le salaire n’est pas daté et ne fait pas de rappel', () => {
    expect(avertissementSalaireNonDate(2100, 2200)).toBe(
      'Changé ici, le salaire n’est pas daté : il remplace 2 100,00 € sur tout bulletin recalculé, ' +
        'sans rappel des mois déjà payés. Pour une augmentation à une date, utilisez « Changer le salaire ».',
    );
  });

  it('rien à dire tant que le champ n’a pas changé', () => {
    expect(avertissementSalaireNonDate(2100, 2100)).toBeNull();
    expect(avertissementSalaireNonDate(2100, '')).toBeNull();
    expect(avertissementSalaireNonDate(null, 2100)).toBeNull();
  });
});
