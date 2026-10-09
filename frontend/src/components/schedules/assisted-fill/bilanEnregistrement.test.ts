import { describe, expect, it } from 'vitest';
import { joursEcritsDuLot, phraseEnregistrement } from './bilanEnregistrement';

describe('joursEcritsDuLot', () => {
  it('prend le nombre de jours écrits du résumé du lot', () => {
    expect(joursEcritsDuLot({ committed_days: 3 }, [{ days: [{ nature: 'reel' }, { nature: 'prevu' }] }])).toBe(3);
  });

  it('sans résumé, ne compte que les jours réels (pas le prévu)', () => {
    expect(
      joursEcritsDuLot(undefined, [
        { days: [{ nature: 'reel' }, { nature: 'prevu' }, { nature: 'reel' }, { nature: 'prevu' }] },
      ]),
    ).toBe(2);
  });
});

describe('phraseEnregistrement', () => {
  it('accorde salarié et jour, sans « (s) »', () => {
    expect(phraseEnregistrement(1, 3)).toBe('1 salarié · 3 jours mis à jour.');
    expect(phraseEnregistrement(2, 1)).toBe('2 salariés · 1 jour mis à jour.');
    expect(phraseEnregistrement(1, 0)).toBe('1 salarié · 0 jour mis à jour.');
  });
});
