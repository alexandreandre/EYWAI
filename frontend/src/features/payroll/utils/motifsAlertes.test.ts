import { describe, expect, it } from 'vitest';

import { estARevoir } from './revueDuMois';
import { motifsDesAlertes } from './motifsAlertes';

describe('une ligne à revoir dit toutes ses alertes', () => {
  const alertes = [
    'Heures supplémentaires élevées : 21,33 h (> 20 h).',
    'Le net à payer a varié de 14,0 % (seuil critique > 10 %).',
  ];

  it('deux alertes : les deux sont dites, pas seulement la première', () => {
    const texte = motifsDesAlertes(alertes);
    expect(texte).toContain(alertes[0]);
    expect(texte).toContain(alertes[1]);
    expect(texte).toBe(`${alertes[0]} · ${alertes[1]}`);
  });

  it('« Net > Brut » reste à côté du nom et ne se répète pas parmi les motifs', () => {
    expect(motifsDesAlertes(['Net > Brut', alertes[0]])).toBe(alertes[0]);
  });

  it('sans alerte, rien', () => {
    expect(motifsDesAlertes([])).toBe('');
  });

  it('la ligne est à revoir dès une alerte', () => {
    expect(
      estARevoir({
        statut: 'success',
        bulletin: { status: 'brouillon' } as never,
        alertes,
        ecart: null,
      })
    ).toBe(true);
  });
});
