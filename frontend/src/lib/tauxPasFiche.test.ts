import { describe, expect, it } from 'vitest';

import { libelleTauxFiche, tauxConnu } from '@/lib/tauxPasFiche';

describe('taux de prélèvement connu ([B1], 12/10/2026)', () => {
  it('le bloc de la fenêtre de création n’est pas un taux', () => {
    expect(tauxConnu({ is_personnalise: false, taux: 0 })).toBeNull();
    expect(tauxConnu(undefined)).toBeNull();
  });

  it('un 0 % transmis par la DGFiP reste un taux', () => {
    expect(tauxConnu({ taux: 0, type_taux: '01' })).toBe(0);
    expect(tauxConnu({ taux: 0, identifiant_taux: '123' })).toBe(0);
    expect(tauxConnu({ taux: 4.3, periode: '2026-06' })).toBe(4.3);
  });

  it('un taux saisi case cochée est un taux', () => {
    expect(tauxConnu({ taux: 0, is_personnalise: true })).toBe(0);
  });

  it('la carte dit que la grille s’applique, pas 0 %', () => {
    expect(libelleTauxFiche({ is_personnalise: false, taux: 0 })).toBe(
      'Aucun taux connu — grille par défaut appliquée',
    );
  });

  it('un taux s’écrit à la française', () => {
    expect(libelleTauxFiche({ taux: 4.3, type_taux: '01' })).toBe('4,3\u00a0%');
    expect(libelleTauxFiche({ taux: 0, type_taux: '01' })).toBe('0\u00a0%');
  });
});
