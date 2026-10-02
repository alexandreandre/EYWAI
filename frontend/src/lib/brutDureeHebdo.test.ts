import { describe, expect, it } from 'vitest';

import { brutMensuelPourDuree } from './brutDureeHebdo';

describe('brutMensuelPourDuree', () => {
  it('ajoute les heures au-delà de 35 h, majorées de 25 %, à un salaire de base à 35 h', () => {
    const ligne = brutMensuelPourDuree(2000, 39, true);
    expect(ligne).toEqual({ heures: 169, brut: 2285.65, baseA35h: true });
  });

  it('garde le montant saisi quand il est déjà le brut pour la durée du contrat', () => {
    const ligne = brutMensuelPourDuree(2000, 39, false);
    expect(ligne).toEqual({ heures: 169, brut: 2000, baseA35h: false });
  });

  it('ne s’affiche pas à 35 h ou sans salaire', () => {
    expect(brutMensuelPourDuree(2000, 35, true)).toBeNull();
    expect(brutMensuelPourDuree(0, 39, false)).toBeNull();
  });
});
