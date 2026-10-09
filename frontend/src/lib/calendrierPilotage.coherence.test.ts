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
    expect(libelleEntetePilotage({ ...base, aSaisir: 2, avecHeuresSurArret: 1 }).texte).toBe(
      'Reste à compléter : 2 calendriers sur 4',
    );
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
