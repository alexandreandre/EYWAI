import { describe, it, expect } from 'vitest';
import {
  avecTotauxCotisations,
  netAPayerApresModification,
  totauxCotisations,
} from './payslipSyntheseNet';

describe('netAPayerApresModification', () => {
  // BUGNY juillet 2026 : net social 2973,61, impôt 65,66, net à payer 2907,95.
  it('suit une correction du net social avant impôt, au centime', () => {
    expect(netAPayerApresModification(2907.95, 'net_social_avant_impot', 2973.61, 2980)).toBe(
      2914.34
    );
  });

  it('retire un impôt qui augmente', () => {
    expect(
      netAPayerApresModification(2907.95, 'impot_prelevement_a_la_source.montant', 65.66, 70)
    ).toBe(2903.61);
  });

  it('ajoute le transport et l’indemnité contractuelle', () => {
    expect(netAPayerApresModification(2907.95, 'remboursement_transport', 0, 36.5)).toBe(2944.45);
    expect(netAPayerApresModification(2907.95, 'indemnite_transport_fixe', 0, 10)).toBe(2917.95);
  });

  it('laisse le net intact sur les champs sans effet direct', () => {
    expect(netAPayerApresModification(2907.95, 'net_imposable', 1931.15, 2000)).toBe(2907.95);
    expect(netAPayerApresModification(2907.95, 'impot_prelevement_a_la_source.taux', 3.4, 5)).toBe(
      2907.95
    );
  });

  it('préserve ce que le moteur avait retiré ou ajouté au net', () => {
    // AGOUMBI janvier 2026 (Zone 404) : net 1953,86 avec acompte 512,52 et
    // transport 36,50 déjà comptés par le moteur. Refaire la formule de
    // l'écran aurait donné 1990,36 : on ne décale que de la saisie.
    expect(netAPayerApresModification(1953.86, 'remboursement_transport', 36.5, 40)).toBe(1957.36);
  });

  it('ne rend jamais de bruit flottant', () => {
    expect(netAPayerApresModification(2907.95, 'net_social_avant_impot', 2973.61, 2973.62)).toBe(
      2907.96
    );
    expect(netAPayerApresModification('2907.95', 'net_social_avant_impot', '2973.61', '')).toBe(
      -65.66
    );
  });
});

describe('totauxCotisations', () => {
  const structure = {
    bloc_principales: [
      { libelle: 'Maladie', montant_salarial: 0, montant_patronal: 200.1 },
      { libelle: 'Vieillesse', montant_salarial: 541.02, montant_patronal: 300.2 },
    ],
    bloc_allegements: [{ libelle: 'RGDU', montant_salarial: 0, montant_patronal: -100.3 }],
    bloc_csg_non_deductible: [{ libelle: 'CSG', montant_salarial: 58.28, montant_patronal: 0 }],
  };

  it('somme les trois blocs au centime', () => {
    expect(totauxCotisations(structure)).toEqual({ total_salarial: 599.3, total_patronal: 400 });
  });

  it('tolère les montants absents ou en texte et les blocs manquants', () => {
    expect(
      totauxCotisations({ bloc_principales: [{ montant_salarial: '12.5' }, null, { x: 1 }] })
    ).toEqual({ total_salarial: 12.5, total_patronal: 0 });
    expect(totauxCotisations(undefined)).toEqual({ total_salarial: 0, total_patronal: 0 });
  });

  it('remet les totaux sur la structure sans toucher aux lignes', () => {
    const resultat = avecTotauxCotisations(structure);
    expect(resultat.total_salarial).toBe(599.3);
    expect(resultat.bloc_principales).toBe(structure.bloc_principales);
  });
});
