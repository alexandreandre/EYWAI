import { describe, expect, it } from 'vitest';

import { brutMensuelPourDuree } from './brutDureeHebdo';

describe('brutMensuelPourDuree', () => {
  it('ajoute les heures au-delà de 35 h, majorées de 25 %', () => {
    const ligne = brutMensuelPourDuree(2000, 39);
    expect(ligne).toEqual({ heures: 169, brut: 2285.65 });
  });

  it('ne s’affiche pas à 35 h ou sans salaire', () => {
    expect(brutMensuelPourDuree(2000, 35)).toBeNull();
    expect(brutMensuelPourDuree(0, 39)).toBeNull();
  });
});
