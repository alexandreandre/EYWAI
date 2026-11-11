import { describe, expect, it } from 'vitest';
import type { LigneCorrigeable } from '@/api/payslips';
import { etatInitial, type EtatCorrections } from './correctionsBulletin';
import {
  annulerLaCorrection,
  autresChamps,
  champPropose,
  correctionEnAttente,
  corrigerLaLigne,
  estRetiree,
  estSurLeNet,
  etapeEnCours,
  familleDuCode,
  libelleDuChamp,
  MOTIFS_PROPOSES,
  nombreDeChangements,
  origineDeLaLigne,
  primeDeLaLigne,
  remettre,
  retirer,
  retraitDeLaLigne,
  saisieDuCode,
  uniteDuChamp,
} from './bulletinACorriger';

const bulletin = {
  calcul_du_brut: [
    { libelle: 'Salaire de base', quantite: 151.67, taux: 14, gain: 2123.38 },
    { libelle: 'Prime de chantier', gain: 100, saisie_id: 's-1' },
  ],
  primes_non_soumises: [{ libelle: 'Panier', montant: 7.5, saisie_id: 's-2' }],
  net_a_payer: 1800,
};

function etat(): EtatCorrections {
  return etatInitial(bulletin, null);
}

const salaire: LigneCorrigeable = {
  code: 'brut:salaire_base', bloc: 'brut', libelle: 'Salaire de base', mode: 'base_ou_taux',
  base: 151.67, taux: 14, montant: 2123.38,
};
const maintien: LigneCorrigeable = {
  code: 'brut:maintien_employeur', bloc: 'brut', libelle: 'Maintien de salaire employeur', mode: 'montant', montant: 312.44,
};
const prime: LigneCorrigeable = {
  code: 'brut:saisie:s-1', bloc: 'brut', libelle: 'Prime de chantier', mode: null,
  raison: 'Une prime saisie se corrige dans « Primes du mois ».', montant: 100,
};
const absence: LigneCorrigeable = {
  code: 'brut:absence_non_remuneree:14-10-26', bloc: 'brut', libelle: 'Absence non rémunérée du 14/10/26', mode: 'montant', retenue: true, montant: 96.92,
};
const regulHeures: LigneCorrigeable = {
  code: 'brut:regularisation_heures:r-9', bloc: 'brut', libelle: 'Rappel d’heures de 09/2026', mode: null, montant: 55.38,
};
const regulCoti: LigneCorrigeable = {
  code: 'cotisation:regularisation:c-4', bloc: 'cotisations', libelle: 'Régularisation vieillesse', mode: null,
};
const vieillesse: LigneCorrigeable = {
  code: 'cotisation:vieillesse_plafonnee', bloc: 'cotisations', libelle: 'Vieillesse plafonnée', mode: 'base_ou_taux',
  base: 2123.38, taux_salarial: 0.069, taux_patronal: 0.0855, montant_salarial: 146.51, montant_patronal: 181.55,
};
const impot: LigneCorrigeable = { code: 'impot', bloc: 'impot', libelle: 'Impôt', mode: 'taux', base: 1700, taux: 2.5, montant: 42.5 };

describe('origine d’une ligne', () => {
  it('lit la famille du code', () => {
    expect(familleDuCode('brut:heures_sup:25#2')).toBe('heures_sup');
    expect(familleDuCode(null)).toBe('');
  });
  it('classe chaque ligne', () => {
    expect(origineDeLaLigne(salaire)).toBe('fiche');
    expect(origineDeLaLigne(absence)).toBe('planning');
    expect(origineDeLaLigne(prime)).toBe('prime');
    expect(origineDeLaLigne(maintien)).toBe('calcul');
    expect(origineDeLaLigne(regulHeures)).toBe('regularisation_heures');
    expect(origineDeLaLigne(regulCoti)).toBe('regularisation_cotisation');
    expect(origineDeLaLigne(vieillesse)).toBe('cotisation');
    expect(origineDeLaLigne(impot)).toBe('impot');
  });
  it('lit l’identifiant de saisie du code', () => {
    expect(saisieDuCode('brut:saisie:s-1')).toBe('s-1');
    expect(saisieDuCode('brut:regularisation_heures:r-9#2')).toBe('r-9');
    expect(saisieDuCode('cotisation:regularisation:c-4')).toBe('c-4');
    expect(saisieDuCode('brut:salaire_base')).toBeNull();
  });
});

describe('champ proposé', () => {
  it('propose la base d’une ligne à base et taux, puis le taux', () => {
    expect(champPropose(salaire)?.cle).toBe('base');
    expect(autresChamps(salaire).map((c) => c.cle)).toEqual(['taux']);
  });
  it('propose le montant d’une ligne au montant', () => {
    expect(champPropose(maintien)?.cle).toBe('montant');
    expect(autresChamps(maintien)).toEqual([]);
  });
  it('ne propose rien pour une ligne qui ne se corrige pas ici', () => {
    expect(champPropose(prime)).toBeNull();
  });
  it('parle comme la RH, avec l’unité', () => {
    expect(libelleDuChamp(salaire, 'base')).toBe('Le bon nombre');
    expect(libelleDuChamp(maintien, 'montant')).toBe('Le bon montant');
    expect(libelleDuChamp(vieillesse, 'taux_salarial')).toBe('Le bon taux salarial');
    expect(uniteDuChamp(maintien, 'montant')).toBe('€');
    expect(uniteDuChamp(salaire, 'base')).toBe('');
    expect(uniteDuChamp(salaire, 'taux')).toBe('€');
    expect(uniteDuChamp(impot, 'taux')).toBe('%');
    expect(uniteDuChamp(vieillesse, 'base')).toBe('€');
    expect(uniteDuChamp(vieillesse, 'taux_patronal')).toBe('%');
  });
});

describe('retirer et remettre', () => {
  it('dit comment chaque ligne se retire', () => {
    expect(retraitDeLaLigne(prime)).toEqual({ type: 'prime', saisieId: 's-1' });
    expect(retraitDeLaLigne(regulHeures)).toEqual({ type: 'regularisation_heures', saisieId: 'r-9' });
    expect(retraitDeLaLigne(regulCoti)).toEqual({ type: 'regularisation_cotisation', saisieId: 'c-4' });
    expect(retraitDeLaLigne(maintien)).toEqual({ type: 'montant_zero' });
    expect(retraitDeLaLigne(salaire)).toBeNull();
    expect(retraitDeLaLigne(absence)).toBeNull();
    expect(retraitDeLaLigne(vieillesse)).toBeNull();
  });
  it('retire une prime puis la remet', () => {
    const apres = retirer(etat(), prime, '');
    expect(apres.primesRetirees).toEqual(['s-1']);
    expect(estRetiree(apres, prime)).toBe(true);
    expect(remettre(apres, prime).primesRetirees).toEqual([]);
  });
  it('retire une ligne calculée par une correction à zéro, motif compris', () => {
    const apres = retirer(etat(), maintien, MOTIFS_PROPOSES[3]);
    expect(apres.correctionsAjoutees).toEqual([
      { ligne: 'brut:maintien_employeur', libelle: 'Maintien de salaire employeur', motif: 'Ligne non due ce mois-ci', montant: 0 },
    ]);
    expect(estRetiree(apres, maintien)).toBe(true);
    expect(remettre(apres, maintien).correctionsAjoutees).toEqual([]);
  });
  it('retire et remet les régularisations', () => {
    const a = retirer(etat(), regulHeures, '');
    expect(a.heuresRegulariseesRetirees).toEqual(['r-9']);
    const b = retirer(a, regulCoti, '');
    expect(b.regularisationsRetirees).toEqual(['c-4']);
    expect(remettre(remettre(b, regulHeures), regulCoti)).toMatchObject({
      heuresRegulariseesRetirees: [],
      regularisationsRetirees: [],
    });
  });
  it('ne fait rien sur une ligne qui ne se retire pas', () => {
    const depart = etat();
    expect(retirer(depart, salaire, 'x')).toBe(depart);
  });
});

describe('corriger une ligne', () => {
  it('remplace la correction en attente de la même ligne', () => {
    const a = corrigerLaLigne(etat(), salaire, 'base', 140, 'Correction d’une erreur de saisie');
    const b = corrigerLaLigne(a, salaire, 'base', 145, 'Correction d’une erreur de saisie');
    expect(b.correctionsAjoutees).toHaveLength(1);
    expect(correctionEnAttente(b, 'brut:salaire_base')?.base).toBe(145);
    expect(annulerLaCorrection(b, 'brut:salaire_base').correctionsAjoutees).toEqual([]);
  });
});

describe('primes', () => {
  it('trouve la prime d’une ligne saisie', () => {
    expect(primeDeLaLigne(etat(), prime)?.libelle).toBe('Prime de chantier');
    expect(primeDeLaLigne(etat(), salaire)).toBeUndefined();
  });
  it('range les primes non soumises et les saisies sur le net dans « Sur le net »', () => {
    const [chantier, panier] = etat().primes;
    expect(estSurLeNet(chantier)).toBe(false);
    expect(estSurLeNet(panier)).toBe(true);
    expect(estSurLeNet({ ...chantier, surLeNet: 'retenue' })).toBe(true);
  });
});

describe('changements et étapes', () => {
  it('compte chaque changement', () => {
    const depart = etat();
    expect(nombreDeChangements(depart, depart)).toBe(0);
    let courant = retirer(depart, prime, '');
    courant = corrigerLaLigne(courant, salaire, 'base', 140, 'Correction d’une erreur de saisie');
    courant = { ...courant, hs25: courant.hs25 + 2 };
    courant = { ...courant, primes: courant.primes.map((p) => (p.saisieId === 's-2' ? { ...p, montant: 9 } : p)) };
    expect(nombreDeChangements(depart, courant)).toBe(4);
  });
  it('dit l’étape en cours', () => {
    expect(etapeEnCours(false, 0)).toBe(1);
    expect(etapeEnCours(true, 0)).toBe(2);
    expect(etapeEnCours(true, 2)).toBe(2);
    expect(etapeEnCours(false, 2)).toBe(3);
  });
});
