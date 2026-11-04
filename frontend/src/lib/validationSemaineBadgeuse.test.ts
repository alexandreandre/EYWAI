import { describe, expect, it } from 'vitest';

import { bilanValidationSemaine } from './validationSemaineBadgeuse';

const ok = { status: 'fulfilled' as const, value: undefined };
const ko = (reason: unknown) => ({ status: 'rejected' as const, reason });

describe('bilanValidationSemaine — « Valider la semaine » dit toujours ce qui s’est passé', () => {
  it('tout validé', () => {
    expect(bilanValidationSemaine([ok, ok, ok], ['2026-10-05', '2026-10-06', '2026-10-07'])).toEqual({
      reussi: true,
      message: 'Semaine validée : 3 jours.',
    });
  });

  it('des jours non validés : combien, lesquels, et la raison du premier échec', () => {
    const erreur = { isAxiosError: true, response: { status: 409, data: { detail: 'Journée déjà clôturée.' } } };
    const bilan = bilanValidationSemaine([ok, ko(erreur), ko(new Error('x'))], ['2026-10-05', '2026-10-06', '2026-10-07']);
    expect(bilan.reussi).toBe(false);
    expect(bilan.message).toBe('2 jours sur 3 non validés (06/10, 07/10).');
    expect(bilan.premierEchec).toBe(erreur);
  });
});
