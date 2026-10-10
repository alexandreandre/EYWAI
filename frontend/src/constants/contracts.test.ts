import { describe, expect, it } from 'vitest';

import {
  AIDE_MAINTIEN_REGIME_APPRENTI,
  CONTRACT_TYPES,
  aideDateFinContrat,
} from './contracts';

describe('aideDateFinContrat', () => {
  it('parle de prime de précarité pour un CDD', () => {
    expect(aideDateFinContrat('CDD')).toContain('prime de précarité');
  });

  it("ne parle pas de prime de précarité pour un stage, qui n'en a pas", () => {
    const aide = aideDateFinContrat('Stage');
    expect(aide).not.toContain('précarité');
    expect(aide.toLowerCase()).toContain('stage');
  });
});

describe('AIDE_MAINTIEN_REGIME_APPRENTI', () => {
  it('dit quand cocher et ce que retient Martine sans date d’exécution', () => {
    expect(AIDE_MAINTIEN_REGIME_APPRENTI).toContain('1er mars 2025');
    expect(AIDE_MAINTIEN_REGIME_APPRENTI).toContain('apprentissage');
    expect(AIDE_MAINTIEN_REGIME_APPRENTI).toContain('Martine');
    expect(AIDE_MAINTIEN_REGIME_APPRENTI).toContain("date d'entrée");
  });
});

describe('CONTRACT_TYPES', () => {
  it('reste la liste de référence des sept types de la fiche', () => {
    expect(CONTRACT_TYPES).toHaveLength(7);
  });
});
