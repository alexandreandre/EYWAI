import { describe, expect, it } from 'vitest';

import { brutMensuelPourDuree, majorationHsDuBareme, texteMajoration } from './brutDureeHebdo';

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

describe('majoration lue du barème des heures supplémentaires ([B15], 12/10/2026)', () => {
  // Le moteur majore les heures structurelles au taux de la première tranche
  // du barème ; l’écran figeait 25 % dans son calcul et dans son texte.
  const rates = {
    heures_supp: {
      config_data: {
        regles_calcul_communes: {
          taux_majoration_par_defaut: {
            heures_supplementaires: [{ taux: 0.1 }, { taux: 0.5 }],
          },
        },
      },
      version: 1,
      last_checked_at: null,
      comment: null,
      source_links: null,
    },
  };

  it('lit le taux de la première tranche', () => {
    expect(majorationHsDuBareme(rates)).toBe(0.1);
    expect(majorationHsDuBareme(undefined)).toBeNull();
    expect(majorationHsDuBareme({})).toBeNull();
  });

  it('le brut suit la majoration donnée', () => {
    // 2 000 € à 35 h, 39 h : 17,33 h × (2 000 / 151,67) € × 1,10 = 251,37 €.
    expect(brutMensuelPourDuree(2000, 39, true, 0.1)?.brut).toBe(2251.37);
  });

  it('le texte dit le taux du barème, à la française', () => {
    expect(texteMajoration(0.25)).toBe('majorées de 25 %');
    expect(texteMajoration(0.1)).toBe('majorées de 10 %');
    expect(texteMajoration(null)).toBe('majorées au taux du barème des heures supplémentaires');
  });
});
