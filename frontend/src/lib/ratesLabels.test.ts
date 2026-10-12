import { describe, expect, it } from 'vitest';

import { formatRateKey } from './ratesLabels';

describe('formatRateKey : les deux SMIC de la page des taux, nommés', () => {
  it('le SMIC de la réduction générale est celui du 1er janvier, pas « SMIC Reference Horaire »', () => {
    expect(formatRateKey('smic_reference_horaire')).toBe(
      'SMIC horaire de référence de la réduction (1er janvier)'
    );
  });

  it('le SMIC du barème est celui en vigueur', () => {
    expect(formatRateKey('smic_horaire_brut')).toBe('SMIC horaire brut en vigueur');
  });
});
