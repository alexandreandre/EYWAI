import { describe, expect, it } from 'vitest';

import { confirmationClotureIjss } from './clotureIjss';

describe('confirmationClotureIjss — la clôture ne part plus sans confirmation', () => {
  it('dit ce qui se ferme, et que l’écran ne rouvre pas', () => {
    expect(confirmationClotureIjss({ libelleMois: 'Octobre 2026', ecarts: 0, enAttente: 0 })).toEqual({
      titre: 'Clôturer Octobre 2026 ?',
      description:
        'Les imports, les synchronisations et « Appliquer validés » seront fermés pour ce mois. L’écran ne permet pas de rouvrir un mois clôturé.',
      confirmer: 'Clôturer le mois',
      destructif: true,
    });
  });

  it('rappelle ce qui reste ouvert', () => {
    expect(confirmationClotureIjss({ libelleMois: 'Octobre 2026', ecarts: 2, enAttente: 1 }).description).toBe(
      'Les imports, les synchronisations et « Appliquer validés » seront fermés pour ce mois. L’écran ne permet pas de rouvrir un mois clôturé. ' +
        'Il reste 2 écarts à traiter et 1 arrêt en attente CPAM.',
    );
    expect(confirmationClotureIjss({ libelleMois: 'Octobre 2026', ecarts: 1, enAttente: 0 }).description).toMatch(
      /Il reste 1 écart à traiter\.$/,
    );
  });
});
