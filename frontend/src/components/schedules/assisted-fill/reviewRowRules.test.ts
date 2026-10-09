import { describe, expect, it } from 'vitest';
import {
  filtreApresAssociation,
  nomsHorsReleve,
  libelleHorsReleve,
  horsReleveRestant,
  reservedEmployeeIds,
  rowCarriesHours,
  statusAfterLosingEmployee,
  visibleRowWarnings,
} from './reviewRowRules';

const travail = (heures: number | null) => ({ heures, type: 'travail' });

describe('rowCarriesHours', () => {
  it('une ligne avec une heure travaillée porte quelque chose', () => {
    expect(rowCarriesHours({ employeeId: 'e1', days: [travail(7.5)] })).toBe(true);
  });

  it('un jour d’absence porte une information même à 0 h', () => {
    expect(
      rowCarriesHours({ employeeId: 'e1', days: [{ heures: 0, type: 'conge' }] }),
    ).toBe(true);
  });

  it('une semaine vide ou à 0 h ne porte rien', () => {
    expect(rowCarriesHours({ employeeId: 'e1', days: [] })).toBe(false);
    expect(rowCarriesHours({ employeeId: 'e1', days: [travail(0), travail(null)] })).toBe(false);
  });
});

describe('reservedEmployeeIds', () => {
  it('une ligne vide ne réserve pas son salarié : on peut l’associer à la ligne qui porte ses heures', () => {
    const rows = [
      { employeeId: 'm1', days: [] },
      { employeeId: 'b1', days: [travail(8)] },
      { employeeId: null, days: [travail(9)] },
    ];
    expect(reservedEmployeeIds(rows)).toEqual(['b1']);
  });
});

describe('statusAfterLosingEmployee', () => {
  it('une ligne vide qui perd son salarié reste « Semaine vide »', () => {
    expect(statusAfterLosingEmployee({ employeeId: 'm1', days: [] })).toBe('empty');
  });

  it('une ligne avec des heures qui perd son salarié attend une association', () => {
    expect(statusAfterLosingEmployee({ employeeId: 'm1', days: [travail(8)] })).toBe('error');
  });
});

describe('visibleRowWarnings', () => {
  it('montre tous les avertissements d’une ligne à vérifier, pas seulement le premier', () => {
    const warnings = [
      'Nom seul « DUPRAT » rapproché de Claire MOREL (nom d’usage) : seul salarié de ce nom.',
      'Relevé à relire — Martine a retenu les heures du badge, pas les annotations : ven 18/09 « +1 ».',
    ];
    expect(visibleRowWarnings(warnings, 'warning')).toEqual(warnings);
  });

  it('ne montre rien sous une ligne prête', () => {
    expect(visibleRowWarnings(['bruit'], 'ok')).toEqual([]);
  });
});

describe('horsReleveRestant', () => {
  it('retire du compteur les salariés associés à la main depuis l’analyse', () => {
    expect(horsReleveRestant(2, ['a'], ['a', 'b'])).toBe(1);
  });

  it('ne bouge pas tant que personne n’est associé', () => {
    expect(horsReleveRestant(2, ['a'], ['a'])).toBe(2);
  });

  it('ne descend jamais sous zéro et ignore les lignes sans salarié', () => {
    expect(horsReleveRestant(1, [], ['a', 'b', null])).toBe(0);
  });

  it('remonte si une association est défaite', () => {
    expect(horsReleveRestant(2, ['a'], [])).toBe(3);
  });
});

describe('filtreApresAssociation', () => {
  it('quitte « À vérifier » pour que la ligne associée reste visible', () => {
    expect(filtreApresAssociation('verify')).toBe('all');
    expect(filtreApresAssociation('incomplete')).toBe('all');
  });

  it('laisse les autres filtres tels quels', () => {
    expect(filtreApresAssociation('all')).toBe('all');
    expect(filtreApresAssociation('ready')).toBe('ready');
  });
});

describe('nomsHorsReleve', () => {
  const roster = [
    { id: 'a', first_name: 'Camille', last_name: 'Roussel' },
    { id: 'b', first_name: 'Léa', last_name: 'Fontaine' },
    { id: 'c', first_name: 'Mathis', last_name: 'Carpentier' },
  ];

  it('nomme les salariés du roster qui ne sont sur aucune ligne', () => {
    expect(nomsHorsReleve(roster, ['a', null, 'c'])).toEqual(['Léa Fontaine']);
  });

  it('libellé court : les noms jusqu’à trois, puis le reste compté', () => {
    expect(libelleHorsReleve(['Léa Fontaine'])).toBe('Léa Fontaine');
    expect(libelleHorsReleve(['A A', 'B B', 'C C', 'D D', 'E E'])).toBe('A A, B B, C C et 2 autres');
    expect(libelleHorsReleve([])).toBe('');
  });
});
