import { describe, expect, it } from 'vitest';

import type { LigneCorrigeable } from '@/api/payslips';
import {
  aideDeLaCorrection,
  apercuDuMontant,
  champsDeLaLigne,
  correctionDeLigne,
  etatInitial,
  eurosFr,
  formulaireDeLaVersion,
  formulaireVide,
  libelleDeLOption,
  recalculAttendu,
  requeteDeCorrection,
  resumeDeLaCorrection,
  resumeDeLaCorrectionAEnregistrer,
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

// Jeu de la carte « Corriger une ligne » du 23/10.
const SALAIRE_CORRIGE: LigneCorrigeable = {
  ...SALAIRE,
  taux: 15,
  montant: 2275.05,
  correction: { ligne: 'brut:salaire_base', libelle: 'Salaire de base', motif: 'Avenant', taux: 15, saisie_id: 'c1' },
  valeur_calculee: { quantite: 151.67, taux: 14.1347, gain: 2143.81, perte: null },
};
const MUTUELLE_CORRIGEE: LigneCorrigeable = {
  code: 'cotisation:mutuelle',
  bloc: 'cotisations',
  libelle: 'Mutuelle',
  mode: 'montant',
  montant_salarial: 20,
  montant_patronal: 17.62,
  correction: { ligne: 'cotisation:mutuelle', libelle: 'Mutuelle', motif: 'Tarif mutuelle erroné', montant_salarial: 20, saisie_id: 'c2' },
  valeur_calculee: { base: null, taux_salarial: null, taux_patronal: null, montant_salarial: 17.62, montant_patronal: 17.62 },
};

describe('motif trop court : un message près du champ, pas un bouton grisé muet', () => {
  it('deux caractères : le message le dit', () => {
    expect(aideDeLaCorrection('20', 'ab')).toEqual({
      champ: 'motif',
      message: 'Le motif doit faire au moins 3 caractères.',
    });
  });

  it('chaque bouton grisé dit pourquoi', () => {
    expect(aideDeLaCorrection('', '')?.message).toContain('valeur voulue');
    expect(aideDeLaCorrection('20', '')?.message).toContain('motif');
    expect(aideDeLaCorrection('vingt', 'Avenant')?.champ).toBe('valeur');
    expect(aideDeLaCorrection('20', 'Avenant')).toBeNull();
  });
});

describe('après un enregistrement, la carte revient à zéro', () => {
  it('une nouvelle version du bulletin vide le formulaire', () => {
    const rempli = { ...formulaireVide('v1'), code: 'brut:salaire_base', cle: 'taux' as const, valeur: '15', motif: 'Avenant' };
    expect(formulaireDeLaVersion(rempli, 'v1')).toBe(rempli);
    expect(formulaireDeLaVersion(rempli, 'v2')).toEqual(formulaireVide('v2'));
  });

  it('« Martine : » dit la valeur que Martine avait calculée, jamais la valeur corrigée', () => {
    const champs = champsDeLaLigne(SALAIRE_CORRIGE);
    expect(champs.find((c) => c.cle === 'taux')?.valeur).toBe(14.1347);
    expect(champs.find((c) => c.cle === 'base')?.valeur).toBe(151.67);
    expect(champsDeLaLigne(MUTUELLE_CORRIGEE).find((c) => c.cle === 'montant_salarial')?.valeur).toBe(17.62);
    const impot = { ...IMPOT, taux: 3.5, correction: { ligne: 'impot', libelle: 'Impôt', motif: 'Taux personnalisé', taux: 3.5 }, valeur_calculee: { taux: 1.3, montant: 26.83 } };
    expect(champsDeLaLigne(impot)[0].valeur).toBe(1.3);
  });

  it('refaire une correction retirée part de la valeur de Martine', () => {
    expect(apercuDuMontant(SALAIRE_CORRIGE, 'base', 160)).toBe(2261.55);
  });
});

describe('une ligne qui se corrige ailleurs dit où', () => {
  it('une prime saisie : « Primes du mois » dans le libellé, pas seulement l’infobulle', () => {
    const prime: LigneCorrigeable = { code: 'brut:saisie:1', bloc: 'brut', libelle: 'Prime de jeu', mode: null, raison: 'Une prime saisie se corrige dans « Primes du mois ».' };
    expect(libelleDeLOption(prime)).toBe('Prime de jeu — se corrige dans « Primes du mois »');
  });

  it('les autres disent ce qu’il faut faire', () => {
    const sousTotal: LigneCorrigeable = { code: 'brut:st', bloc: 'brut', libelle: 'SOUS-TOTAL', mode: null, raison: 'Un sous-total ne se corrige pas : corrigez les lignes qui le composent.' };
    expect(libelleDeLOption(sousTotal)).toBe('SOUS-TOTAL — sous-total : corrigez ses lignes');
    expect(libelleDeLOption(SALAIRE)).toBe('Salaire de base');
  });
});

describe('une cotisation corrigée sur une part : le résumé montre cette part', () => {
  it('la part salariale de la mutuelle, pas la somme des deux parts', () => {
    expect(resumeDeLaCorrection(MUTUELLE_CORRIGEE)).toBe('Martine : 17,62 € → corrigé : 20,00 € (part salariale)');
  });

  it('une base corrigée change les deux parts : le résumé le dit', () => {
    const maladie: LigneCorrigeable = {
      ...MALADIE,
      base: 2100,
      montant_patronal: 147,
      taux_salarial: 0.01,
      montant_salarial: 21,
      correction: { ligne: MALADIE.code ?? '', libelle: 'Maladie', motif: 'Base', base: 2100, saisie_id: 'c3' },
      valeur_calculee: { base: 2000, taux_salarial: 0.01, taux_patronal: 0.07, montant_salarial: 20, montant_patronal: 140 },
    };
    expect(resumeDeLaCorrection(maladie)).toBe('Martine : 160,00 € → corrigé : 168,00 € (salarié + employeur)');
  });
});

describe('une correction à enregistrer montre la valeur voulue et celle de Martine', () => {
  it('le taux du salaire de base', () => {
    const correction = correctionDeLigne(SALAIRE, 'taux', 15, 'Avenant');
    expect(resumeDeLaCorrectionAEnregistrer(correction, SALAIRE)).toBe(
      'Taux — Martine : 16,4832 → voulu : 15 · montant après correction : 2 275,05 €'
    );
  });

  it('un taux de cotisation se lit en pourcentage', () => {
    const correction = correctionDeLigne(MALADIE, 'taux_patronal', 7.3, 'Taux AT');
    expect(resumeDeLaCorrectionAEnregistrer(correction, MALADIE)).toBe(
      'Taux patronal (%) — Martine : 7 → voulu : 7,3 · montant après correction : 146,00 €'
    );
  });
});
