import { describe, expect, it } from 'vitest';
import { lireMethodeIndemniteCpFinCdd } from './indemniteCpFinCddSettings';

describe('lireMethodeIndemniteCpFinCdd', () => {
  it('vaut la règle légale tant que rien n’est choisi', () => {
    expect(lireMethodeIndemniteCpFinCdd(undefined)).toBe('remuneration_versee');
    expect(lireMethodeIndemniteCpFinCdd({ settings: {} } as never)).toBe('remuneration_versee');
  });

  it('lit la méthode enregistrée', () => {
    expect(
      lireMethodeIndemniteCpFinCdd({
        settings: { indemnite_cp_fin_cdd: 'salaire_retabli_solde_n1' },
      } as never)
    ).toBe('salaire_retabli_solde_n1');
  });

  it('ramène une valeur inconnue à la règle légale', () => {
    expect(
      lireMethodeIndemniteCpFinCdd({ settings: { indemnite_cp_fin_cdd: 'quadra' } } as never)
    ).toBe('remuneration_versee');
  });
});
