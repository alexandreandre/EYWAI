import { describe, expect, it } from 'vitest';
import {
  cleJourExistant,
  joursRemplaces,
  phraseJoursRemplaces,
  suiteResultatJoursRemplaces,
} from './joursDejaSaisis';

const jour = (j: number, heures: number | null, nature: 'prevu' | 'reel' = 'reel') => ({
  jour: j,
  heures,
  nature,
  annee: 2026,
  mois: 10,
});

const ligne = (nom: string, employeeId: string | null, jours: ReturnType<typeof jour>[], enregistrable = true) => ({
  nom,
  employeeId,
  enregistrable,
  jours,
});

const existant = (valeurs: Record<number, number | null>) =>
  Object.fromEntries(Object.entries(valeurs).map(([j, h]) => [cleJourExistant(2026, 10, Number(j)), h]));

describe('joursRemplaces — heures réelles déjà saisies que l’import va écraser', () => {
  it('compte les jours dont les heures saisies changent, par salarié', () => {
    const res = joursRemplaces(
      [ligne('Élodie Test', 'e1', [jour(5, 6), jour(6, 6), jour(7, 8)])],
      { e1: existant({ 5: 7, 6: 7, 7: 8 }) },
    );
    expect(res).toEqual([{ nom: 'Élodie Test', jours: 2 }]);
  });

  it('ne compte pas un jour sans heures déjà saisies, ni un jour inchangé', () => {
    const res = joursRemplaces(
      [ligne('A', 'e1', [jour(5, 6), jour(6, 6)])],
      { e1: existant({ 5: null, 6: 6 }) },
    );
    expect(res).toEqual([]);
  });

  it('ignore le prévu, les lignes non enregistrées et les salariés sans rapprochement', () => {
    expect(joursRemplaces([ligne('A', 'e1', [jour(5, 6, 'prevu')])], { e1: existant({ 5: 7 }) })).toEqual([]);
    expect(joursRemplaces([ligne('A', 'e1', [jour(5, 6)], false)], { e1: existant({ 5: 7 }) })).toEqual([]);
    expect(joursRemplaces([ligne('A', null, [jour(5, 6)])], {})).toEqual([]);
  });

  it('une valeur écrite à 0 h sur 7 h saisies est bien un remplacement', () => {
    expect(joursRemplaces([ligne('A', 'e1', [jour(5, 0)])], { e1: existant({ 5: 7 }) })).toEqual([
      { nom: 'A', jours: 1 },
    ]);
  });
});

describe('phrases', () => {
  const l = [
    { nom: 'Élodie Test', jours: 2 },
    { nom: 'Mathis Test', jours: 1 },
  ];

  it('avant : dit combien, pour qui, et que l’import remplace', () => {
    expect(phraseJoursRemplaces(l)).toBe(
      '3 jours déjà saisis seront remplacés par l’import : Élodie Test (2 jours), Mathis Test (1 jour).',
    );
    expect(phraseJoursRemplaces([{ nom: 'A', jours: 1 }])).toBe(
      '1 jour déjà saisi sera remplacé par l’import : A (1 jour).',
    );
    expect(phraseJoursRemplaces([])).toBeNull();
  });

  it('après : le résultat le redit', () => {
    expect(suiteResultatJoursRemplaces(l)).toBe(
      ' Jours déjà saisis remplacés : Élodie Test (2 jours), Mathis Test (1 jour).',
    );
    expect(suiteResultatJoursRemplaces([])).toBe('');
  });
});
