import { describe, expect, it } from 'vitest';
import { SALAIRE_MENSUEL_MAXIMUM, alerteSalaireInhabituel } from './salaireVraisemblable';

describe('alerteSalaireInhabituel', () => {
  it('un salaire courant ne dit rien', () => {
    expect(alerteSalaireInhabituel(1990.001)).toBeNull();
    expect(alerteSalaireInhabituel(6696.67)).toBeNull();
  });

  it('une virgule avalée par le navigateur est signalée, avec le montant lu', () => {
    // « 1800,5 » lu 18005 par un navigateur qui n'est pas en français.
    expect(alerteSalaireInhabituel(18005)?.replace(/\s/g, ' ')).toMatch(/18 005 €/);
    expect(alerteSalaireInhabituel(18005)).toMatch(/virgule/);
  });

  it('rien à dire sans montant', () => {
    expect(alerteSalaireInhabituel('')).toBeNull();
    expect(alerteSalaireInhabituel(undefined)).toBeNull();
  });

  it('le plafond refusé reste au-dessus de tout salaire mensuel plausible', () => {
    expect(SALAIRE_MENSUEL_MAXIMUM).toBe(100000);
  });
});
