import { describe, expect, it } from 'vitest';
import { presentationLigneEnErreur } from './ligneEnErreur';

describe("ligne d'un bulletin non généré", () => {
  it('un refus de la paie se dit « Refusé », avec un bouton neutre « Générer »', () => {
    expect(presentationLigneEnErreur(true)).toEqual({ badge: 'Refusé', bouton: 'Générer', boutonRouge: false });
  });

  it('une vraie panne reste « Échec », avec « Réessayer » en rouge', () => {
    expect(presentationLigneEnErreur(false)).toEqual({ badge: 'Échec', bouton: 'Réessayer', boutonRouge: true });
    expect(presentationLigneEnErreur(undefined)).toEqual({ badge: 'Échec', bouton: 'Réessayer', boutonRouge: true });
  });
});
