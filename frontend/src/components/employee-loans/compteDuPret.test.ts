import { describe, expect, it } from 'vitest';

import { compteDuPretSaisi } from './compteDuPret';

// Un compte par prêt dans l'OD de paie (04/11/2026) : le compte que la
// comptabilité ouvre pour chaque prêt (42511000, 42590009…).

describe('compte comptable du prêt', () => {
  it('garde les chiffres, sans les espaces', () => {
    expect(compteDuPretSaisi(' 4251 1000 ')).toEqual({ compte: '42511000', erreur: null });
  });

  it('une case vide laisse le compte de la société', () => {
    expect(compteDuPretSaisi('')).toEqual({ compte: null, erreur: null });
    expect(compteDuPretSaisi('   ')).toEqual({ compte: null, erreur: null });
  });

  it.each(['4251-1000', 'compte courant', '42', '1'.repeat(21)])('« %s » est refusé', (saisi) => {
    const { compte, erreur } = compteDuPretSaisi(saisi);
    expect(compte).toBeNull();
    expect(erreur).toMatch(/chiffres/);
  });
});
