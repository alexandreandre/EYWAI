import { describe, expect, it } from 'vitest';
import { joursNonLus, phraseJoursNonLus, suiteResultatJoursNonLus } from './joursNonLus';

const ligne = (nom: string, attendus: number | null, lus: number | null, enregistrable = true) => ({
  nom,
  joursAttendus: attendus,
  joursLus: lus,
  enregistrable,
});

describe('joursNonLus', () => {
  it('compte les jours que la feuille n’a pas permis de lire, par salarié enregistré', () => {
    expect(
      joursNonLus([ligne('Élodie Vasseur', 5, 3), ligne('Léa Fontaine', 5, 5), ligne('Mathis', 5, 4)]),
    ).toEqual([
      { nom: 'Élodie Vasseur', jours: 2 },
      { nom: 'Mathis', jours: 1 },
    ]);
  });

  it('ignore une ligne non enregistrée ou sans décompte', () => {
    expect(joursNonLus([ligne('A', 5, 3, false), ligne('B', null, null)])).toEqual([]);
  });
});

describe('phrases', () => {
  const l = [
    { nom: 'Élodie Vasseur', jours: 2 },
    { nom: 'Mathis', jours: 1 },
  ];

  it('avant : dit combien et pour qui, et que les jours restent à saisir', () => {
    expect(phraseJoursNonLus(l)).toBe(
      '3 jours non lus ne seront pas écrits et restent à saisir au calendrier : Élodie Vasseur (2 jours), Mathis (1 jour).',
    );
    expect(phraseJoursNonLus([])).toBeNull();
  });

  it('après : le résultat les nomme aussi', () => {
    expect(suiteResultatJoursNonLus(l)).toBe(
      ' Jours non lus, à saisir au calendrier : Élodie Vasseur (2 jours), Mathis (1 jour).',
    );
    expect(suiteResultatJoursNonLus([])).toBe('');
  });
});
