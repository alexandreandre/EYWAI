import { describe, expect, it } from 'vitest';
import { messageDepartCree } from './messageDepartCree';
import { CONTRAT_ABSENT_MESSAGE } from '@/components/exits/CreateExitDialog';

describe('message de départ créé', () => {
  it('dit ce qui a été créé, pour qui, à quelle date, et la suite', () => {
    const m = messageDepartCree('fin_cdd', '2026-10-31', 'Inès Martin');
    expect(m.title).toBe('Départ créé');
    expect(m.description).toContain('Fin de CDD');
    expect(m.description).toContain('Inès Martin');
    expect(m.description).toContain('31/10/2026');
    expect(m.description).toContain('bulletin de sortie');
  });

  it("le message d'absence de contrat ne prétend pas que la fiche vient d'un autre logiciel", () => {
    expect(CONTRAT_ABSENT_MESSAGE).not.toContain('repris');
    expect(CONTRAT_ABSENT_MESSAGE).toContain('Aucun contrat');
  });
});
