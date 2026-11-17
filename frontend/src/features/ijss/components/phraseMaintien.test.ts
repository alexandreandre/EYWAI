import { describe, expect, it } from 'vitest';
import type { ArretDuMois } from '@/api/ijssTracking';
import { phraseMaintien } from './ArretsDuMoisPanel';

const arret = (etat: ArretDuMois['maintien']['etat']) =>
  ({ maintien: { etat, montant_verse: 0, montant_en_attente: 0, motif: null } }) as ArretDuMois;

describe('phraseMaintien', () => {
  it("dit qu'un bulletin calculé avant l'arrêt est à régénérer", () => {
    const p = phraseMaintien(arret('bulletin_a_recalculer'));
    expect(p.texte).toContain("avant l'arrêt");
    expect(p.ton).toBe('attente');
  });
});
