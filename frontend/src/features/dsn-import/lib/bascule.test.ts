import { describe, expect, it } from 'vitest';

import { libelleBascule } from '@/features/dsn-import/lib/bascule';

describe('bascule de reprise affichée ([B13], 12/10/2026)', () => {
  it('dit quel logiciel a payé jusqu’à quand, et depuis quand Martine calcule', () => {
    expect(
      libelleBascule({
        dernier_mois_repris: '2026-08',
        premier_mois_calcule: '2026-09',
        logiciel_precedent: 'Quadra',
        source: 'bulletins',
      }),
    ).toBe('Paie reprise de Quadra au 31/08/2026 : Martine calcule la paie depuis septembre 2026.');
  });

  it('sans logiciel nommé', () => {
    expect(
      libelleBascule({ dernier_mois_repris: '2025-12', premier_mois_calcule: '2026-01', logiciel_precedent: null }),
    ).toBe('Paie reprise de l’ancien logiciel au 31/12/2025 : Martine calcule la paie depuis janvier 2026.');
  });

  it('sans bascule, le dit', () => {
    expect(libelleBascule(null)).toBe(
      'Aucune reprise posée : ni date de bascule, ni solde d’ouverture repris d’un ancien logiciel.',
    );
  });
});
