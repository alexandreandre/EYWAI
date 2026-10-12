import { describe, expect, it } from 'vitest';

import { aideLignesPrevoyance } from '@/features/employees/utils/prevoyance';

describe('aide sous la prévoyance ([B4], 12/10/2026)', () => {
  it('un cadre sans ligne : aucune cotisation, il faut saisir les lignes', () => {
    expect(aideLignesPrevoyance(true, 0)).toBe(
      'Saisissez les lignes du contrat de prévoyance : sans ligne, le bulletin d’un cadre ne porte aucune cotisation de prévoyance.',
    );
  });

  it('un non-cadre sans ligne : le barème national', () => {
    expect(aideLignesPrevoyance(false, 0)).toBe('Sans ligne saisie, le barème national s’applique au bulletin.');
  });

  it('avec des lignes, aucune aide', () => {
    expect(aideLignesPrevoyance(true, 2)).toBeNull();
    expect(aideLignesPrevoyance(false, 1)).toBeNull();
  });
});
