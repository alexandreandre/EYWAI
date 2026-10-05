import { describe, expect, it } from 'vitest';
import { lireMontantNegocie } from './montantNegocie';

describe('lireMontantNegocie', () => {
  it('lit un montant à la française', () => {
    expect(lireMontantNegocie('15 000,50')).toEqual({ valeur: 15000.5 });
    expect(lireMontantNegocie('12000')).toEqual({ valeur: 12000 });
    expect(lireMontantNegocie(' 8 500.25 € ')).toEqual({ valeur: 8500.25 });
  });

  it('un champ vide revient au minimum légal', () => {
    expect(lireMontantNegocie('')).toEqual({ valeur: null });
    expect(lireMontantNegocie('   ')).toEqual({ valeur: null });
  });

  it('refuse un montant négatif ou illisible, en disant quoi taper', () => {
    expect(lireMontantNegocie('-10')).toEqual({ erreur: 'Saisissez un montant positif, par exemple 12 500,00.' });
    expect(lireMontantNegocie('douze mille')).toEqual({
      erreur: 'Saisissez un montant positif, par exemple 12 500,00.',
    });
  });
});
