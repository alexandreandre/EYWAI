import { describe, expect, it } from 'vitest';
import { computeGlobalKpis, type EmployeeCalendarOverviewRow } from './schedulesOverview';
import { libelleEntetePilotage, pastilleSaisieDuMois } from './calendrierPilotage';

const ligne = (
  rowStatus: EmployeeCalendarOverviewRow['rowStatus'],
  joursHeuresSurArret: number[] = [],
) =>
  ({
    employee: { id: Math.random().toString(), first_name: 'A', last_name: 'B' },
    planned: [],
    actual: [],
    heuresPrevues: 0,
    heuresFaites: 0,
    ecart: 0,
    rowStatus,
    absenceConflictDays: [],
    joursHeuresSurArret,
    loadError: false,
    isForfaitJour: false,
  }) as EmployeeCalendarOverviewRow;

describe('en-tête du pilotage avec des heures sur un jour d’arrêt', () => {
  it('un salarié complet mais en conflit n’est pas compté prêt (pourcentage)', () => {
    const k = computeGlobalKpis([ligne('saisi'), ligne('saisi'), ligne('saisi_avec_ecart', [19, 20]), ligne('saisi')]);
    expect(k.avecHeuresSurArret).toBe(1);
    expect(k.progressPercent).toBe(75);
  });

  it('sans conflit, tout saisi fait 100 %', () => {
    const k = computeGlobalKpis([ligne('saisi'), ligne('saisi_avec_ecart')]);
    expect(k.avecHeuresSurArret).toBe(0);
    expect(k.progressPercent).toBe(100);
  });

  it('l’en-tête ne dit « prêts pour la paie » que sans reste à saisir ni conflit', () => {
    const base = { aSaisir: 0, avecHeuresSurArret: 0, total: 4 };
    expect(libelleEntetePilotage(base)).toEqual({ ton: 'ok', texte: 'Tous les calendriers sont prêts pour la paie' });
    expect(libelleEntetePilotage({ ...base, avecHeuresSurArret: 1 })).toEqual({
      ton: 'alerte',
      texte: '1 calendrier porte des heures pendant un arrêt : à corriger avant la paie',
    });
    expect(libelleEntetePilotage({ ...base, aSaisir: 2, avecHeuresSurArret: 0 })).toEqual({
      ton: 'neutre',
      texte: 'Reste à compléter : 2 calendriers sur 4',
    });
  });

  /**
   * Tournage C1 (18/10/2026) : un calendrier à saisir et un autre portant des
   * heures sur un arrêt ; l'en-tête disait « Reste à compléter : 1 calendrier
   * sur 4 » (50 %), sans l'alerte ambre, et ne comptait pas le calendrier en
   * conflit, qui n'est pas prêt non plus.
   */
  it('à saisir ET en conflit : l’alerte ambre compte les deux', () => {
    const k = computeGlobalKpis([ligne('a_saisir'), ligne('saisi_avec_ecart', [19]), ligne('saisi'), ligne('saisi')]);
    expect(k.progressPercent).toBe(50);
    expect(libelleEntetePilotage(k)).toEqual({
      ton: 'alerte',
      texte:
        'Reste à compléter : 2 calendriers sur 4, dont 1 qui porte des heures pendant un arrêt : à corriger avant la paie',
    });
  });

  it('un calendrier à saisir qui porte aussi des heures sur un arrêt ne compte qu’une fois', () => {
    const k = computeGlobalKpis([ligne('a_saisir', [3]), ligne('saisi'), ligne('saisi'), ligne('saisi')]);
    expect(libelleEntetePilotage(k)).toEqual({
      ton: 'alerte',
      texte:
        'Reste à compléter : 1 calendrier sur 4, dont 1 qui porte des heures pendant un arrêt : à corriger avant la paie',
    });
  });
});

describe('pastille de saisie du tiroir', () => {
  it('« Saisi » sans conflit, « À saisir » sinon', () => {
    expect(pastilleSaisieDuMois('saisi', [])).toBe('Saisi');
    expect(pastilleSaisieDuMois('a_saisir', [])).toBe('À saisir');
  });

  it('un mois saisi avec des heures sur un arrêt n’est pas « Saisi »', () => {
    expect(pastilleSaisieDuMois('saisi', [19, 20])).toBe('Heures sur un arrêt');
    expect(pastilleSaisieDuMois('a_saisir', [19])).toBe('À saisir');
  });
});
