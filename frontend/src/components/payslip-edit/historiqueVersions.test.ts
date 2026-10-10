import { describe, expect, it } from 'vitest';

import {
  VERSIONS_CONSERVEES,
  libelleBoutonRestaurer,
  phraseConservation,
  textesConfirmationRestauration,
} from './historiqueVersions';

describe('phraseConservation', () => {
  it('dit le plafond de versions conservées', () => {
    expect(VERSIONS_CONSERVEES).toBe(10);
    expect(phraseConservation([3, 4])).toContain('10 dernières versions');
  });

  it("à la dixième, prévient que la plus ancienne partira à la prochaine", () => {
    const versions = [12, 13, 14, 15, 16, 17, 18, 19, 20, 21];
    const phrase = phraseConservation(versions);
    expect(phrase).toContain('version 12');
    expect(phrase).toContain('prochaine');
    expect(phrase).toContain('PDF');
  });

  it("avant la dixième, ne fait pas peur", () => {
    expect(phraseConservation([1, 2, 3])).not.toContain('prochaine');
  });
});

describe('textesConfirmationRestauration', () => {
  const t = textesConfirmationRestauration(4);

  it('dit exactement ce qui est rétabli et ce qui ne l’est pas', () => {
    expect(t.titre).toBe('Restaurer la version 4 ?');
    expect(t.description).toContain('heures sup');
    expect(t.description).toContain('primes');
    expect(t.description).toContain('recalculé');
    expect(t.description).toMatch(/ne reviennent pas|reste/);
  });

  it('le bouton confirme l’action, pas « OK »', () => {
    expect(t.confirmer).toBe('Restaurer ces heures sup et ces primes');
  });
});

describe('libelleBoutonRestaurer', () => {
  it('ne promet pas toute la version', () => {
    expect(libelleBoutonRestaurer).toBe('Restaurer heures sup et primes');
  });
});
