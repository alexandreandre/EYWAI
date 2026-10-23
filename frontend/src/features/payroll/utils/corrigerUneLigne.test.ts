import { describe, expect, it } from 'vitest';

import type { LigneCorrigeable } from '@/api/payslips';
import {
  apercuDuMontant,
  champsDeLaLigne,
  correctionDeLigne,
  etatInitial,
  eurosFr,
  recalculAttendu,
  requeteDeCorrection,
  resumeDeLaCorrection,
} from './correctionsBulletin';

const SALAIRE: LigneCorrigeable = {
  code: 'brut:salaire_base',
  bloc: 'brut',
  libelle: 'Salaire de base',
  mode: 'base_ou_taux',
  base: 151.67,
  taux: 16.4832,
  montant: 2500,
};
const MALADIE: LigneCorrigeable = {
  code: 'cotisation:securite_sociale_maladie',
  bloc: 'cotisations',
  libelle: 'Maladie',
  mode: 'base_ou_taux',
  base: 2000,
  taux_salarial: 0,
  taux_patronal: 0.07,
  montant_salarial: 0,
  montant_patronal: 140,
};
const IMPOT: LigneCorrigeable = {
  code: 'impot',
  bloc: 'impot',
  libelle: 'Impôt sur le revenu prélevé à la source',
  mode: 'taux',
  base: 2063.56,
  taux: 5.2,
  montant: 107.31,
};

describe('corriger une ligne', () => {
  it('une ligne en heures se corrige par sa base ou son taux', () => {
    expect(champsDeLaLigne(SALAIRE).map((c) => c.cle)).toEqual(['base', 'taux']);
  });

  it('une ligne au forfait se corrige par son montant, et une retenue le dit', () => {
    expect(champsDeLaLigne({ ...SALAIRE, mode: 'montant', retenue: true })).toEqual([
      { cle: 'montant', libelle: 'Retenue (€)', valeur: 2500 },
    ]);
  });

  it('une ligne qui ne se corrige pas ici ne propose rien', () => {
    expect(champsDeLaLigne({ ...SALAIRE, mode: null, raison: 'Une prime saisie se corrige dans « Primes du mois ».' })).toEqual([]);
  });

  it('une cotisation montre ses taux en pourcentage et la correction les envoie en fraction', () => {
    const champs = champsDeLaLigne(MALADIE);
    expect(champs.map((c) => c.cle)).toEqual(['base', 'taux_salarial', 'taux_patronal']);
    expect(champs[2].valeur).toBeCloseTo(7);
    expect(correctionDeLigne(MALADIE, 'taux_patronal', 7.3, ' Taux AT 2026 ')).toEqual({
      ligne: 'cotisation:securite_sociale_maladie',
      libelle: 'Maladie',
      motif: 'Taux AT 2026',
      taux_patronal: 0.073,
    });
  });

  it('l’aperçu suit base × taux au centime', () => {
    expect(apercuDuMontant(SALAIRE, 'base', 160)).toBe(2637.31);
    expect(apercuDuMontant(MALADIE, 'base', 2100)).toBe(147);
    expect(apercuDuMontant(IMPOT, 'taux', 7.5)).toBe(154.77);
    expect(apercuDuMontant(SALAIRE, 'base', Number.NaN)).toBeNull();
  });

  it('le résumé dit ce que Martine avait calculé et ce qui est imposé', () => {
    const corrigee: LigneCorrigeable = {
      ...SALAIRE,
      base: 160,
      montant: 2637.31,
      correction: { ligne: 'brut:salaire_base', libelle: 'Salaire de base', motif: 'Avenant', base: 160, saisie_id: 'c1' },
      valeur_calculee: { quantite: 151.67, taux: 16.4832, gain: 2500, perte: null },
    };
    expect(resumeDeLaCorrection(corrigee)).toBe('Martine : 2 500,00 € → corrigé : 2 637,31 €');
    expect(eurosFr(-1234.5)).toBe('−1 234,50 €');
  });

  it('la requête porte les corrections ajoutées et retirées, et le bulletin sera recalculé', () => {
    const initial = etatInitial({}, null);
    expect(initial.correctionsAjoutees).toEqual([]);
    const courant = {
      ...initial,
      correctionsAjoutees: [correctionDeLigne(SALAIRE, 'base', 160, 'Avenant')],
      correctionsRetirees: ['c9'],
    };
    const requete = requeteDeCorrection(initial, courant, null);
    expect(requete.corrections.corrections_ajoutees).toEqual([
      { ligne: 'brut:salaire_base', libelle: 'Salaire de base', motif: 'Avenant', base: 160 },
    ]);
    expect(requete.corrections.corrections_retirees).toEqual(['c9']);
    expect(recalculAttendu(initial, courant)).toBe(true);
  });
});
