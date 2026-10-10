import { describe, expect, it } from 'vitest';

import { chargerCatalogueDePrimes } from './catalogueDePrimes';

describe('chargerCatalogueDePrimes', () => {
  it('rend les primes du catalogue quand le chargement réussit', async () => {
    const r = await chargerCatalogueDePrimes(async () => ({ data: [{ id: 'p1', libelle: 'Prime' }] }));
    expect(r).toEqual({ primes: [{ id: 'p1', libelle: 'Prime' }], echec: null });
  });

  it("dit pourquoi la liste est vide et quoi faire quand le chargement échoue", async () => {
    const r = await chargerCatalogueDePrimes(async () => {
      throw new Error('réseau');
    });
    expect(r.primes).toEqual([]);
    expect(r.echec).toContain('catalogue des primes');
    expect(r.echec).toContain('saisissez le nom');
  });
});
