import { describe, expect, it } from 'vitest';

import { lireTauxSaisi, tauxAffiche, tauxEnSaisie } from './tauxSociete';

/**
 * Réglages de la société, « Taux spécifiques » (vidéo G, 11/10/2026) : MAJI
 * affichait « Taux Accident Travail (AT/MP) 70.00 % » alors que le bulletin
 * applique 0,70 % (15,75 € sur 2 250 €). Les taux sont enregistrés en points de
 * pourcentage (MAJI 0.70, Colorplast 3.15, FNAL de Colorplast 0.10) : l'écran
 * multipliait par 100 tout taux inférieur à 1.
 */
describe('taux de la société à l’écran', () => {
  it('affiche le taux enregistré tel quel, à la française', () => {
    expect(tauxAffiche(0.7)).toBe('0,70 %');
    expect(tauxAffiche(3.15)).toBe('3,15 %');
    expect(tauxAffiche(0.1)).toBe('0,10 %');
    expect(tauxAffiche(0)).toBe('0,00 %');
  });

  it('dit qu’un taux manque', () => {
    expect(tauxAffiche(null)).toBe('N/A');
    expect(tauxAffiche(undefined)).toBe('N/A');
  });
});

describe('saisie du taux AT/MP', () => {
  it('« 0,70 » reste 0,70 %', () => {
    const lu = lireTauxSaisi('0,70');
    expect(lu).toEqual({ valeur: 0.7 });
    expect(tauxAffiche(0.7)).toBe('0,70 %');
  });

  it('accepte le point et les espaces', () => {
    expect(lireTauxSaisi(' 3.66 ')).toEqual({ valeur: 3.66 });
  });

  it('vide : rien n’est envoyé', () => {
    expect(lireTauxSaisi('  ')).toEqual({ valeur: undefined });
  });

  it('refuse ce qui n’est pas un nombre', () => {
    expect(lireTauxSaisi('abc')).toEqual({ erreur: 'Indiquez un nombre, par exemple 3,66.' });
  });

  it('le champ repart du taux enregistré, avec une virgule', () => {
    expect(tauxEnSaisie(0.7)).toBe('0,7');
    expect(tauxEnSaisie(null)).toBe('');
  });
});
