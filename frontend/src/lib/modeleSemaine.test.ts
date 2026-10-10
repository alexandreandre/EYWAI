import { describe, expect, it } from 'vitest';

import { modeleSemaineDuSalarie } from './modeleSemaine';

// Octobre 2026 : le 1er est un jeudi.
const jour = (j: number, type: string, heures: number | null) => ({ jour: j, type, heures_prevues: heures });

describe('modeleSemaineDuSalarie', () => {
  it('reprend le prévu actuel du salarié, jour de semaine par jour de semaine', () => {
    const prevu = [
      jour(1, 'travail', 7), // jeudi
      jour(2, 'travail', 7), // vendredi
      jour(3, 'weekend', 0),
      jour(5, 'travail', 7), // lundi
      jour(6, 'travail', 7), // mardi
      jour(7, 'travail', 7), // mercredi
    ];
    expect(modeleSemaineDuSalarie({ prevu, year: 2026, month: 10, dureeHebdo: 35, forfaitJour: false })).toEqual({
      1: '7', 2: '7', 3: '7', 4: '7', 5: '7',
    });
  });

  it('sans prévu saisi, répartit la durée hebdomadaire du contrat sur cinq jours (35 h : 7 h)', () => {
    const prevu = [jour(1, 'travail', null), jour(2, 'travail', null)];
    expect(modeleSemaineDuSalarie({ prevu, year: 2026, month: 10, dureeHebdo: 35, forfaitJour: false })).toEqual({
      1: '7', 2: '7', 3: '7', 4: '7', 5: '7',
    });
    expect(modeleSemaineDuSalarie({ prevu: [], year: 2026, month: 10, dureeHebdo: 39, forfaitJour: false })[1]).toBe('7.8');
  });

  it('ni prévu ni durée connue : des cases vides, jamais les heures d’une autre personne', () => {
    expect(modeleSemaineDuSalarie({ prevu: [], year: 2026, month: 10, dureeHebdo: null, forfaitJour: false })).toEqual({
      1: '', 2: '', 3: '', 4: '', 5: '',
    });
  });

  it('un jour férié ou un congé ne donne pas son jour de semaine', () => {
    const prevu = [jour(1, 'ferie', 0), jour(8, 'travail', 7)]; // deux jeudis
    expect(modeleSemaineDuSalarie({ prevu, year: 2026, month: 10, dureeHebdo: 35, forfaitJour: false })[4]).toBe('7');
  });

  it('forfait jours : un jour par jour ouvré', () => {
    expect(modeleSemaineDuSalarie({ prevu: [], year: 2026, month: 10, dureeHebdo: null, forfaitJour: true })).toEqual({
      1: '1', 2: '1', 3: '1', 4: '1', 5: '1',
    });
  });
});
