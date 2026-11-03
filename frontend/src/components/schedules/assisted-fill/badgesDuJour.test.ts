import { describe, expect, it } from 'vitest';
import { libelleBadges } from './badgesDuJour';

describe('badges bruts d’un jour, à côté des heures retenues', () => {
  it('écrit l’entrée et la sortie lues dans le relevé', () => {
    expect(libelleBadges('800', '1547')).toBe('badges 8 h 00 → 15 h 47');
    expect(libelleBadges('2000', '400')).toBe('badges 20 h 00 → 4 h 00');
  });
  it('dit ce qui manque', () => {
    expect(libelleBadges('800', null)).toBe('badges 8 h 00 → pas de sortie');
    expect(libelleBadges(null, '400')).toBe('badges pas d’entrée → 4 h 00');
    expect(libelleBadges('800', '0')).toBe('badges 8 h 00 → pas de sortie');
  });
  it('rien quand le relevé ne donne pas de badges', () => {
    expect(libelleBadges(null, null)).toBeNull();
    expect(libelleBadges('', undefined)).toBeNull();
  });
  it('lit aussi l’écriture 8:00', () => {
    expect(libelleBadges('08:00', '15:45')).toBe('badges 8 h 00 → 15 h 45');
  });
});
