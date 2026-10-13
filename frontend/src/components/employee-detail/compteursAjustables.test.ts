import { describe, expect, it } from 'vitest';

import { compteurAjustable } from './compteursAjustables';

describe('compteurs corrigés au crayon de la fiche (décision du 12/10)', () => {
  it('RTT et JTC se corrigent en jours', () => {
    expect(compteurAjustable('RTT')).toEqual({ compteur: 'rtt', unite: 'j' });
    expect(compteurAjustable('JTC')).toEqual({ compteur: 'jtc', unite: 'j' });
  });

  it('le repos compensateur se corrige en heures, avec motif, comme les RTT', () => {
    expect(compteurAjustable('Repos compensateur')).toEqual({
      compteur: 'repos_compensateur',
      unite: 'h',
    });
  });

  it('les congés payés passent par le recalage, pas par ce crayon', () => {
    expect(compteurAjustable('Congés Payés')).toBeUndefined();
  });
});
