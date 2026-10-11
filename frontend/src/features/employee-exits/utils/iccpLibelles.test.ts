import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import { libelleMethodeIccp, lignesDesPeriodes } from './iccpLibelles';

/**
 * Détail de l'indemnité de congés du dossier : l'estimation suit la règle par
 * période du bulletin ; « L1243-8 » est l'article de la précarité, pas des congés.
 */
describe('détail de l’indemnité de congés du dossier', () => {
  it('nomme les méthodes sans article de la précarité', () => {
    expect(libelleMethodeIccp('par_periode')).toBe('Par période, le plus favorable');
    expect(libelleMethodeIccp('dixieme_global')).toBe('1/10e de la rémunération du contrat');
    expect(libelleMethodeIccp('l1243_8')).toBe('1/10e de la rémunération du contrat');
    expect(libelleMethodeIccp('maintien')).toBe('Maintien de salaire');
    expect(libelleMethodeIccp('dixieme')).toBe('Règle du 1/10e');
  });

  it('écrit une ligne par période', () => {
    expect(
      lignesDesPeriodes({
        periodes: [
          { libelle: '2025-2026', restants: 15, droits: 30, dixieme: 1800, maintien: 1628.25, retenu: 1800, methode: 'dixieme' },
          { libelle: '2026-2027', restants: 2, droits: 2.5, dixieme: null, maintien: 216, retenu: 216, methode: 'maintien_seul' },
        ],
      })
    ).toEqual([
      'Période 2025-2026 : 15 j restants sur 30 — 1/10e 1 800,00 € ou maintien 1 628,25 € → 1 800,00 €',
      'Période 2026-2027 : 2 j restants sur 2,5 — rémunération inconnue, maintien 216,00 € → 216,00 €',
    ]);
  });

  it('l’écran n’écrit plus « L1243-8 »', () => {
    const source = readFileSync(path.resolve(__dirname, '../IccpArbitrageDetail.tsx'), 'utf-8');
    expect(source).not.toContain('L1243');
  });
});
