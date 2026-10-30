import { describe, expect, it } from 'vitest';
import { lienModifierFiche, ouvreLaModification } from './lienModification';

describe('lien qui ouvre la modification de la fiche', () => {
  it('mène à la fiche du salarié, formulaire ouvert', () => {
    expect(lienModifierFiche('e1')).toBe('/employees/e1?modifier=fiche');
  });

  it('se reconnaît à l’arrivée sur la fiche, et seulement lui', () => {
    expect(ouvreLaModification('?modifier=fiche')).toBe(true);
    expect(ouvreLaModification('?year=2026&month=10&modifier=fiche')).toBe(true);
    expect(ouvreLaModification('')).toBe(false);
    expect(ouvreLaModification('?tab=documents')).toBe(false);
  });
});
