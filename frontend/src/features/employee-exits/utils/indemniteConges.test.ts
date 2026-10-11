import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import { indemniteCongesAffichee, totalBrutDesIndemnites } from './indemniteConges';

/**
 * Onglet « Indemnités » d'un départ : l'indemnité de congés affichée est celle
 * du bulletin de sortie dès qu'il existe (fin de CDD de septembre 2026 : onglet
 * 274,59 €, bulletin 164,04 €), et l'onglet n'écrit plus un « Total net estimé »
 * égal au brut.
 */
describe('indemnité de congés de l’onglet Indemnités', () => {
  it('sans bulletin de sortie, affiche l’estimation du dossier', () => {
    expect(indemniteCongesAffichee(274.59, null)).toEqual({ montant: 274.59, source: 'estimation' });
    expect(indemniteCongesAffichee(274.59, undefined)).toEqual({ montant: 274.59, source: 'estimation' });
  });

  it('avec le bulletin de sortie, affiche ce qu’il a versé', () => {
    expect(
      indemniteCongesAffichee(274.59, { mois: '09/2026', indemnite_conges: 164.04 })
    ).toEqual({ montant: 164.04, source: 'bulletin', mois: '09/2026', estimation: 274.59 });
  });

  it('un bulletin qui n’a rien versé dit zéro, pas l’estimation', () => {
    expect(
      indemniteCongesAffichee(1294.4, { mois: '09/2026', indemnite_conges: 0 })
    ).toEqual({ montant: 0, source: 'bulletin', mois: '09/2026', estimation: 1294.4 });
  });

  it('le total brut reprend le montant affiché', () => {
    expect(totalBrutDesIndemnites(1294.4, 1294.4, { mois: '09/2026', indemnite_conges: 0 })).toBe(0);
    expect(totalBrutDesIndemnites(1294.4, 1294.4, null)).toBe(1294.4);
    expect(totalBrutDesIndemnites(2500, 274.59, { mois: '09/2026', indemnite_conges: 164.04 })).toBe(2389.45);
  });

  it('l’onglet n’écrit plus « Total net estimé »', () => {
    const source = readFileSync(
      path.resolve(__dirname, '../../../components/exits/ExitDetailsPanel.tsx'),
      'utf-8'
    );
    expect(source).not.toContain('Total net estimé');
  });
});
