import { describe, expect, it } from 'vitest';

import { lignesIgnorees, phraseLignesIgnorees, suiteResultatLignesIgnorees } from './lignesIgnorees';

const travail = [{ heures: 7, type: 'travail' }];

const ligne = (over: Partial<Parameters<typeof lignesIgnorees>[0][number]>) => ({
  rawName: 'Camou Cam',
  employeeId: null as string | null,
  days: travail,
  enregistrable: false,
  ...over,
});

describe('lignesIgnorees', () => {
  it('nomme une ligne sans salarié associé qui porte des heures', () => {
    expect(lignesIgnorees([ligne({})])).toEqual([
      { nom: 'Camou Cam', raison: 'aucun salarié associé' },
    ]);
  });

  it('ne compte pas une ligne enregistrable ni une ligne sans heures', () => {
    expect(
      lignesIgnorees([
        ligne({ employeeId: 'e1', enregistrable: true }),
        ligne({ rawName: 'Vide', days: [] }),
        ligne({ rawName: 'Zéro', days: [{ heures: 0, type: 'travail' }] }),
      ]),
    ).toEqual([]);
  });

  it('dit pourquoi une ligne associée mais à vérifier est laissée', () => {
    expect(lignesIgnorees([ligne({ rawName: 'Léa', employeeId: 'e2' })])).toEqual([
      { nom: 'Léa', raison: 'à vérifier (cochez « Inclure écarts / match douteux »)' },
    ]);
  });
});

describe('phraseLignesIgnorees', () => {
  it('rien à dire quand tout est enregistré', () => {
    expect(phraseLignesIgnorees([])).toBeNull();
  });

  it('compte, nomme et donne la raison, au singulier comme au pluriel', () => {
    expect(phraseLignesIgnorees([{ nom: 'Camou Cam', raison: 'aucun salarié associé' }])).toBe(
      '1 ligne ne sera pas enregistrée : « Camou Cam » (aucun salarié associé).',
    );
    expect(
      phraseLignesIgnorees([
        { nom: 'A', raison: 'aucun salarié associé' },
        { nom: 'B', raison: 'aucun salarié associé' },
      ]),
    ).toBe('2 lignes ne seront pas enregistrées : « A » (aucun salarié associé), « B » (aucun salarié associé).');
  });
});

describe('suiteResultatLignesIgnorees', () => {
  it('le résultat nomme les lignes non enregistrées', () => {
    expect(suiteResultatLignesIgnorees([{ nom: 'Camou Cam', raison: 'aucun salarié associé' }])).toBe(
      ' Non enregistré : « Camou Cam » (aucun salarié associé).',
    );
    expect(suiteResultatLignesIgnorees([])).toBe('');
  });
});
