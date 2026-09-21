import { describe, expect, it } from 'vitest';
import { lireCompensationSemaines } from './compensationSemainesSettings';

describe('lireCompensationSemaines', () => {
  it('vaut faux tant que la société n’a jamais coché l’option', () => {
    expect(lireCompensationSemaines(undefined)).toBe(false);
    expect(lireCompensationSemaines({ settings: {} } as never)).toBe(false);
  });

  it('lit le booléen enregistré', () => {
    expect(
      lireCompensationSemaines({ settings: { compensation_heures_entre_semaines: true } } as never)
    ).toBe(true);
    expect(
      lireCompensationSemaines({ settings: { compensation_heures_entre_semaines: false } } as never)
    ).toBe(false);
  });

  it('ne prend pas une chaîne pour un oui', () => {
    expect(
      lireCompensationSemaines({ settings: { compensation_heures_entre_semaines: 'true' } } as never)
    ).toBe(false);
  });
});
