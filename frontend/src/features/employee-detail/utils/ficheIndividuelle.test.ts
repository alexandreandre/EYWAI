import { describe, expect, it } from 'vitest';

import { messagePeriode, periodeParDefaut } from './ficheIndividuelle';

describe('fiche individuelle : la période (lot L18)', () => {
  it('par défaut, l’année civile en cours', () => {
    expect(periodeParDefaut(new Date(2026, 10, 27))).toEqual({ debut: '2026-01', fin: '2026-12' });
  });

  it('une période valide n’a pas de message', () => {
    expect(messagePeriode({ debut: '2025-11', fin: '2026-10' })).toBeNull();
  });

  it('dit pourquoi une période est refusée', () => {
    expect(messagePeriode({ debut: '', fin: '2026-12' })).toMatch(/premier mois/);
    expect(messagePeriode({ debut: '2026-12', fin: '2026-01' })).toMatch(/après le dernier/);
    expect(messagePeriode({ debut: '2022-01', fin: '2026-12' })).toMatch(/36 mois/);
  });
});
