import { describe, expect, it } from 'vitest';
import { documentModifiable } from './documentsSortie';

// [H14] « Modifier le document » menait, pour une attestation de portabilité, à
// « L'édition de ce type de document n'est pas encore supportée. » : le bouton
// ne s'affiche que pour un type qui a un éditeur.
describe('documents de sortie : lesquels se modifient', () => {
  it('le certificat, l’attestation employeur et le solde de tout compte ont un éditeur', () => {
    expect(documentModifiable('certificat_travail')).toBe(true);
    expect(documentModifiable('attestation_pole_emploi')).toBe(true);
    expect(documentModifiable('solde_tout_compte')).toBe(true);
  });

  it('les attestations de portabilité et les pièces téléversées n’en ont pas', () => {
    expect(documentModifiable('attestation_portabilite_mutuelle')).toBe(false);
    expect(documentModifiable('attestation_portabilite_prevoyance')).toBe(false);
    expect(documentModifiable('recu_solde_compte')).toBe(false);
    expect(documentModifiable('lettre_demission')).toBe(false);
  });
});
