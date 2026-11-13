import { describe, expect, it } from 'vitest';
import type { LigneCorrigeable } from '@/api/payslips';
import { etatInitial, type EtatCorrections } from './correctionsBulletin';
import {
  annulerLaCorrection,
  autresChamps,
  autresMontantsDuNet,
  champPropose,
  correctionEnAttente,
  corrigerLaLigne,
  cotisationsAOuvrir,
  estRetiree,
  estSurLeNet,
  etapeEnCours,
  familleDuCode,
  lierLeReport,
  libelleDuChamp,
  MOTIFS_PROPOSES,
  nombreDeChangements,
  origineDeLaLigne,
  primeDeLaLigne,
  remettre,
  retirer,
  retraitDeLaLigne,
  saisieDuCode,
  suiviDesLignes,
  uniteDuChamp,
  valeurEnAttente,
  versionAAnnuler,
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

/** Le même bulletin, avec une régularisation d'heures et une de cotisation imprimées. */
function etatAvecRegularisations(): EtatCorrections {
  return {
    ...etat(),
    heuresRegularisees: [{ saisieId: 'r-9', libelle: 'Rappel d’heures', motif: 'Oubli', quantite: 4, taux: 13.85, montant: 55.38 }],
    regularisations: [{ saisieId: 'c-4', libelle: 'Régularisation vieillesse', motif: 'Oubli', montantSalarial: 3, montantPatronal: 4 }],
  };
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
    expect(libelleDuChamp(vieillesse, 'base')).toBe('Le bon montant soumis');
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
    const avec = etatAvecRegularisations();
    expect(retraitDeLaLigne(prime, avec)).toEqual({ type: 'prime', saisieId: 's-1' });
    expect(retraitDeLaLigne(regulHeures, avec)).toEqual({ type: 'regularisation_heures', saisieId: 'r-9' });
    expect(retraitDeLaLigne(regulCoti, avec)).toEqual({ type: 'regularisation_cotisation', saisieId: 'c-4' });
    expect(retraitDeLaLigne(maintien, avec)).toEqual({ type: 'montant_zero' });
    expect(retraitDeLaLigne(salaire, avec)).toBeNull();
    expect(retraitDeLaLigne(absence, avec)).toBeNull();
    expect(retraitDeLaLigne(vieillesse, avec)).toBeNull();
  });
  it('ne propose pas la poubelle d’une régularisation inconnue des saisies du bulletin', () => {
    // Un code au slug (ancienne régularisation) : rien à envoyer au serveur, donc pas de poubelle.
    expect(retraitDeLaLigne(regulHeures, etat())).toBeNull();
    expect(retraitDeLaLigne(regulCoti, etat())).toBeNull();
    expect(retirer(etat(), regulHeures, '')).toEqual(etat());
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
    const a = retirer(etatAvecRegularisations(), regulHeures, '');
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
    expect(annulerLaCorrection(b, salaire).correctionsAjoutees).toEqual([]);
  });
  it('remplace une correction déjà posée : sa saisie part dans les corrections retirées', () => {
    const corrigee: LigneCorrigeable = { ...maintien, correction: { ligne: maintien.code!, libelle: maintien.libelle, motif: 'Avant', montant: 300, saisie_id: 'corr-1' } };
    const a = corrigerLaLigne(etat(), corrigee, 'montant', 320, 'Correction d’une erreur de calcul');
    expect(a.correctionsRetirees).toEqual(['corr-1']);
    expect(a.correctionsAjoutees).toHaveLength(1);
    // Refaite deux fois : la saisie n'est retirée qu'une fois.
    expect(corrigerLaLigne(a, corrigee, 'montant', 330, 'Correction d’une erreur de calcul').correctionsRetirees).toEqual(['corr-1']);
    const annulee = annulerLaCorrection(a, corrigee);
    expect(annulee.correctionsAjoutees).toEqual([]);
    expect(annulee.correctionsRetirees).toEqual([]);
  });
  it('retire à zéro une ligne déjà corrigée en remplaçant sa correction, et la remet', () => {
    const corrigee: LigneCorrigeable = { ...maintien, correction: { ligne: maintien.code!, libelle: maintien.libelle, motif: 'Avant', montant: 300, saisie_id: 'corr-1' } };
    const a = retirer(etat(), corrigee, MOTIFS_PROPOSES[3]);
    expect(a.correctionsRetirees).toEqual(['corr-1']);
    expect(remettre(a, corrigee).correctionsRetirees).toEqual([]);
  });
  it('annuler sans correction en attente ne touche pas aux corrections retirées', () => {
    const corrigee: LigneCorrigeable = { ...maintien, correction: { ligne: maintien.code!, libelle: maintien.libelle, motif: 'Avant', montant: 300, saisie_id: 'corr-1' } };
    const depart = { ...etat(), correctionsRetirees: ['corr-1'] };
    expect(annulerLaCorrection(depart, corrigee)).toBe(depart);
  });
  it('reporte une correction en attente sur la ligne corrigée, et l’annule avec elle', () => {
    const a = corrigerLaLigne(etat(), maintien, 'montant', 10, 'Rappel', { reporteDe: 'att-1' });
    expect(a.correctionsRetirees).toEqual(['att-1']);
    expect(annulerLaCorrection(a, maintien, { reporteDe: 'att-1' }).correctionsRetirees).toEqual([]);
  });
  it('le lien du report vit hors de la ligne : annuler après un remontage libère la correction reportée', () => {
    // La ligne a perdu son état local : seul le lien gardé par la page dit le report.
    const reports = lierLeReport({}, maintien.code!, 'att-1');
    const a = corrigerLaLigne(etat(), maintien, 'montant', 10, 'Rappel', { reporteDe: 'att-1', reports });
    expect(a.correctionsRetirees).toEqual(['att-1']);
    expect(annulerLaCorrection(a, maintien, { reports }).correctionsRetirees).toEqual([]);
    expect(lierLeReport(reports, maintien.code!, null)).toEqual({});
  });
  it('remettre une ligne retirée à zéro libère la correction reportée', () => {
    const reports = lierLeReport({}, maintien.code!, 'att-1');
    const a = corrigerLaLigne(etat(), maintien, 'montant', 0, 'Ligne non due ce mois-ci', { reporteDe: 'att-1', reports });
    expect(estRetiree(a, maintien)).toBe(true);
    expect(remettre(a, maintien, { reports }).correctionsRetirees).toEqual([]);
  });
  it('garde la correction reportée retirée tant qu’une autre ligne la reporte encore', () => {
    let reports = lierLeReport({}, maintien.code!, 'att-1');
    let courant = corrigerLaLigne(etat(), maintien, 'montant', 10, 'Rappel', { reporteDe: 'att-1', reports });
    reports = lierLeReport(reports, salaire.code!, 'att-1');
    courant = corrigerLaLigne(courant, salaire, 'base', 140, 'Rappel', { reporteDe: 'att-1', reports });
    const sansMaintien = annulerLaCorrection(courant, maintien, { reports });
    expect(sansMaintien.correctionsRetirees).toEqual(['att-1']);
    const sansRien = annulerLaCorrection(sansMaintien, salaire, { reports: lierLeReport(reports, maintien.code!, null) });
    expect(sansRien.correctionsRetirees).toEqual([]);
  });
  it('un lien de report sans correction en attente ne retient pas la correction reportée', () => {
    let reports = lierLeReport({}, maintien.code!, 'att-1');
    reports = lierLeReport(reports, salaire.code!, 'att-1');
    // Seule la ligne du maintien a une correction : le lien du salaire est périmé.
    const a = corrigerLaLigne(etat(), maintien, 'montant', 10, 'Rappel', { reporteDe: 'att-1', reports });
    expect(annulerLaCorrection(a, maintien, { reports }).correctionsRetirees).toEqual([]);
  });
  it('garde retirée la correction posée que la RH avait déjà retirée avant le crayon', () => {
    const corrigee: LigneCorrigeable = { ...maintien, correction: { ligne: maintien.code!, libelle: maintien.libelle, motif: 'Avant', montant: 300, saisie_id: 'corr-1' } };
    const depart = { ...etat(), correctionsRetirees: ['corr-1'] };
    const a = corrigerLaLigne(depart, corrigee, 'montant', 320, 'Correction d’une erreur de calcul', { garderLaCorrectionPoseeRetiree: true });
    const annulee = annulerLaCorrection(a, corrigee, { garderLaCorrectionPoseeRetiree: true });
    expect(annulee.correctionsAjoutees).toEqual([]);
    expect(annulee.correctionsRetirees).toEqual(['corr-1']);
  });
  it('relit la valeur d’une correction en attente, taux en pourcentage', () => {
    const a = corrigerLaLigne(etat(), vieillesse, 'taux_salarial', 7.1, 'Correction d’une erreur de calcul');
    expect(valeurEnAttente(correctionEnAttente(a, vieillesse.code))).toEqual({ cle: 'taux_salarial', valeur: 7.1 });
    const b = corrigerLaLigne(etat(), maintien, 'montant', 0, 'Ligne non due ce mois-ci');
    expect(valeurEnAttente(correctionEnAttente(b, maintien.code))).toEqual({ cle: 'montant', valeur: 0 });
    expect(valeurEnAttente(undefined)).toBeNull();
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
  it('compte une seule fois une prime retirée après avoir été modifiée', () => {
    const depart = etat();
    let courant = { ...depart, primes: depart.primes.map((p) => (p.saisieId === 's-1' ? { ...p, montant: 150 } : p)) };
    courant = retirer(courant, prime, '');
    expect(nombreDeChangements(depart, courant)).toBe(1);
  });
  it('suit les lignes ouvertes : une ligne prête (valeur et motif) n’est plus « en édition »', () => {
    const depart = corrigerLaLigne(etat(), maintien, 'montant', 10, 'Correction d’une erreur de calcul');
    const statuts = new Map([
      ['brut:maintien_employeur', 'edition' as const],
      ['brut:salaire_base', 'sans_motif' as const],
      ['impot', 'edition' as const],
    ]);
    expect(suiviDesLignes(statuts, depart)).toEqual({ enEdition: 2, sansMotif: 1 });
    expect(suiviDesLignes(new Map(), depart)).toEqual({ enEdition: 0, sansMotif: 0 });
  });
  it('dit l’étape en cours', () => {
    expect(etapeEnCours(false, 0)).toBe(1);
    expect(etapeEnCours(true, 0)).toBe(2);
    expect(etapeEnCours(true, 2)).toBe(2);
    expect(etapeEnCours(false, 2)).toBe(3);
  });
});

describe('montants sur le net', () => {
  const aLaSource = [
    { libelle: 'Panier', montant: 7.5, source: '« Primes du mois »' },
    { libelle: 'Titres-restaurant', montant: -40, source: 'la fiche du salarié' },
  ];
  it('cache un montant déjà montré comme prime, d’après l’état du serveur', () => {
    // Comparé à l'état courant, un montant en cours de modification faisait
    // réapparaître la prime en double : la comparaison se fait à l'état initial.
    expect(autresMontantsDuNet(aLaSource, etat()).map((b) => b.libelle)).toEqual(['Titres-restaurant']);
  });
});

describe('bloc des cotisations', () => {
  const cotisations = [vieillesse, { ...regulCoti, alerte: null }];
  it('reste replié sans raison de l’ouvrir', () => {
    expect(cotisationsAOuvrir(cotisations, etat(), new Map(), null)).toBe(false);
  });
  it('s’ouvre pour une cotisation en cours, en alerte, visée par l’onglet « Bulletin » ou changée', () => {
    expect(cotisationsAOuvrir(cotisations, etat(), new Map([[vieillesse.code!, 'edition' as const]]), null)).toBe(true);
    expect(cotisationsAOuvrir([{ ...vieillesse, alerte: 'À relire' }], etat(), new Map(), null)).toBe(true);
    expect(cotisationsAOuvrir(cotisations, etat(), new Map(), { carte: 'ligne', code: vieillesse.code!, jeton: 1 })).toBe(true);
    expect(cotisationsAOuvrir(cotisations, etat(), new Map(), { carte: 'ligne', code: 'brut:salaire_base', jeton: 1 })).toBe(false);
    const change = corrigerLaLigne(etat(), vieillesse, 'base', 2000, 'Correction d’une erreur de calcul');
    expect(cotisationsAOuvrir(cotisations, change, new Map(), null)).toBe(true);
  });
});

describe('annuler l’application', () => {
  const versions = [
    { version: 2, previous_payslip_data: { net_a_payer: 850 } },
    { version: 3, previous_payslip_data: { net_a_payer: 900 } },
  ];
  it('remet la dernière version quand c’est celle de cette application', () => {
    expect(versionAAnnuler(versions, { version: 3, netAvant: 900 })).toBe(3);
  });
  it('se passe des contrôles absents', () => {
    expect(versionAAnnuler(versions, { version: null, netAvant: null })).toBe(3);
    expect(versionAAnnuler([{ version: 3, previous_payslip_data: {} }], { version: null, netAvant: 900 })).toBe(3);
  });
  it('refuse une autre version arrivée depuis, ou un net d’avant qui ne correspond pas', () => {
    expect(versionAAnnuler([...versions, { version: 4, previous_payslip_data: { net_a_payer: 912 } }], { version: 3, netAvant: 900 })).toBeNull();
    expect(versionAAnnuler(versions, { version: null, netAvant: 777 })).toBeNull();
    expect(versionAAnnuler([], { version: null, netAvant: null })).toBeNull();
  });
});
