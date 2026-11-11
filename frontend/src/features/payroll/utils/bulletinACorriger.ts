/**
 * L'onglet « Corriger » est le bulletin lui-même (design du 11/11/2026,
 * retours de Lyon). Ici, la logique pure : d'où vient une ligne, ce qu'on y
 * corrige, comment elle se retire. Rien n'est calculé ici : toute correction
 * reste une variable du mois, recalculée en entier par Martine.
 */
import type { CorrectionLigneAjoutee, LigneCorrigeable } from '@/api/payslips';
import {
  champsDeLaLigne,
  correctionDeLigne,
  type ChampCorrigeable,
  type ChampDeLigne,
  type EtatCorrections,
  type PrimeDuBulletin,
} from './correctionsBulletin';

/** Imprimés sur le bulletin du salarié : jamais un mot sur Quadra ou sur l'outil. */
export const MOTIFS_PROPOSES: readonly string[] = [
  'Correction d’une erreur de calcul',
  'Correction d’une erreur de saisie',
  'Rappel d’un mois précédent',
  'Ligne non due ce mois-ci',
];

export type OrigineDeLigne =
  | 'fiche'
  | 'planning'
  | 'prime'
  | 'regularisation_heures'
  | 'regularisation_cotisation'
  | 'calcul'
  | 'cotisation'
  | 'impot';

const FAMILLES_DE_LA_FICHE = new Set(['salaire_base', 'avantages_en_nature']);
const FAMILLES_DU_PLANNING = new Set([
  'heures_sup',
  'hs_structurelles',
  'heures_complementaires',
  'heures_nuit',
  'pause_remuneree',
  'absence_entree_sortie',
  'absence_injustifiee',
  'absence_non_remuneree',
  'absence_evenement_familial',
  'absence_ferie_non_paye',
  'absence_maladie',
  'absence_conges_payes',
  'indemnite_conges_payes',
  'reduction_hs_absence',
  'reduction_hs_evenement_familial',
]);

/** « brut:heures_sup:25#2 » → « heures_sup ». */
export function familleDuCode(code: string | null | undefined): string {
  if (!code) return '';
  return code.split('#')[0].split(':')[1] ?? '';
}

export function origineDeLaLigne(ligne: Pick<LigneCorrigeable, 'code' | 'bloc'>): OrigineDeLigne {
  if (ligne.bloc === 'impot') return 'impot';
  const code = ligne.code ?? '';
  if (ligne.bloc === 'cotisations') {
    return code.startsWith('cotisation:regularisation:') ? 'regularisation_cotisation' : 'cotisation';
  }
  const famille = familleDuCode(code);
  if (famille === 'saisie') return 'prime';
  if (famille === 'regularisation_heures') return 'regularisation_heures';
  if (FAMILLES_DE_LA_FICHE.has(famille)) return 'fiche';
  if (FAMILLES_DU_PLANNING.has(famille)) return 'planning';
  return 'calcul';
}

const PREFIXES_DE_SAISIE = ['brut:saisie:', 'brut:regularisation_heures:', 'cotisation:regularisation:'];

/** L'identifiant de la saisie porté par le code d'une prime ou d'une régularisation. */
export function saisieDuCode(code: string | null | undefined): string | null {
  const sansNumero = (code ?? '').split('#')[0];
  const prefixe = PREFIXES_DE_SAISIE.find((p) => sansNumero.startsWith(p));
  const id = prefixe ? sansNumero.slice(prefixe.length) : '';
  return id || null;
}

/** Le champ que l'écran propose d'abord : celui que la règle 3 permet, la base avant le taux. */
export function champPropose(ligne: LigneCorrigeable): ChampDeLigne | null {
  return champsDeLaLigne(ligne)[0] ?? null;
}

export function autresChamps(ligne: LigneCorrigeable): ChampDeLigne[] {
  return champsDeLaLigne(ligne).slice(1);
}

export function libelleDuChamp(ligne: LigneCorrigeable, cle: ChampCorrigeable): string {
  switch (cle) {
    case 'base':
      return ligne.bloc === 'cotisations' ? 'La bonne base' : 'Le bon nombre';
    case 'taux':
      return 'Le bon taux';
    case 'taux_salarial':
      return 'Le bon taux salarial';
    case 'taux_patronal':
      return 'Le bon taux patronal';
    case 'montant_salarial':
      return 'La bonne part salariale';
    case 'montant_patronal':
      return 'La bonne part patronale';
    default:
      return 'Le bon montant';
  }
}

export function uniteDuChamp(ligne: LigneCorrigeable, cle: ChampCorrigeable): string {
  if (cle === 'montant' || cle === 'montant_salarial' || cle === 'montant_patronal') return '€';
  if (cle === 'taux_salarial' || cle === 'taux_patronal') return '%';
  if (cle === 'taux') return ligne.bloc === 'impot' ? '%' : '€';
  return ligne.bloc === 'cotisations' ? '€' : '';
}

export type Retrait =
  | { type: 'prime' | 'regularisation_heures' | 'regularisation_cotisation'; saisieId: string }
  | { type: 'montant_zero' };

/** Comment la ligne se retire, ou null : elle se corrige au crayon ou à sa source. */
export function retraitDeLaLigne(ligne: LigneCorrigeable): Retrait | null {
  const origine = origineDeLaLigne(ligne);
  const saisieId = saisieDuCode(ligne.code);
  if (saisieId && (origine === 'prime' || origine === 'regularisation_heures' || origine === 'regularisation_cotisation')) {
    return { type: origine, saisieId };
  }
  if (origine === 'calcul' && ligne.bloc === 'brut' && ligne.mode === 'montant' && !ligne.retenue) {
    return { type: 'montant_zero' };
  }
  return null;
}

export function correctionEnAttente(
  etat: EtatCorrections,
  code: string | null | undefined
): CorrectionLigneAjoutee | undefined {
  return code ? etat.correctionsAjoutees.find((c) => c.ligne === code) : undefined;
}

export function annulerLaCorrection(etat: EtatCorrections, code: string | null | undefined): EtatCorrections {
  if (!code || !correctionEnAttente(etat, code)) return etat;
  return { ...etat, correctionsAjoutees: etat.correctionsAjoutees.filter((c) => c.ligne !== code) };
}

export function corrigerLaLigne(
  etat: EtatCorrections,
  ligne: LigneCorrigeable,
  cle: ChampCorrigeable,
  valeur: number,
  motif: string
): EtatCorrections {
  const sans = annulerLaCorrection(etat, ligne.code);
  return { ...sans, correctionsAjoutees: [...sans.correctionsAjoutees, correctionDeLigne(ligne, cle, valeur, motif)] };
}

const ajouter = (liste: string[], id: string) => (liste.includes(id) ? liste : [...liste, id]);
const enlever = (liste: string[], id: string) => liste.filter((x) => x !== id);

export function estRetiree(etat: EtatCorrections, ligne: LigneCorrigeable): boolean {
  const retrait = retraitDeLaLigne(ligne);
  if (!retrait) return false;
  switch (retrait.type) {
    case 'prime':
      return etat.primesRetirees.includes(retrait.saisieId);
    case 'regularisation_heures':
      return etat.heuresRegulariseesRetirees.includes(retrait.saisieId);
    case 'regularisation_cotisation':
      return etat.regularisationsRetirees.includes(retrait.saisieId);
    default:
      return correctionEnAttente(etat, ligne.code)?.montant === 0;
  }
}

export function retirer(etat: EtatCorrections, ligne: LigneCorrigeable, motif: string): EtatCorrections {
  const retrait = retraitDeLaLigne(ligne);
  if (!retrait) return etat;
  switch (retrait.type) {
    case 'prime':
      return { ...etat, primesRetirees: ajouter(etat.primesRetirees, retrait.saisieId) };
    case 'regularisation_heures':
      return { ...etat, heuresRegulariseesRetirees: ajouter(etat.heuresRegulariseesRetirees, retrait.saisieId) };
    case 'regularisation_cotisation':
      return { ...etat, regularisationsRetirees: ajouter(etat.regularisationsRetirees, retrait.saisieId) };
    default:
      return corrigerLaLigne(etat, ligne, 'montant', 0, motif);
  }
}

export function remettre(etat: EtatCorrections, ligne: LigneCorrigeable): EtatCorrections {
  const retrait = retraitDeLaLigne(ligne);
  if (!retrait) return etat;
  switch (retrait.type) {
    case 'prime':
      return { ...etat, primesRetirees: enlever(etat.primesRetirees, retrait.saisieId) };
    case 'regularisation_heures':
      return { ...etat, heuresRegulariseesRetirees: enlever(etat.heuresRegulariseesRetirees, retrait.saisieId) };
    case 'regularisation_cotisation':
      return { ...etat, regularisationsRetirees: enlever(etat.regularisationsRetirees, retrait.saisieId) };
    default:
      return annulerLaCorrection(etat, ligne.code);
  }
}

export function primeDeLaLigne(etat: EtatCorrections, ligne: LigneCorrigeable): PrimeDuBulletin | undefined {
  if (origineDeLaLigne(ligne) !== 'prime') return undefined;
  const saisieId = saisieDuCode(ligne.code);
  return etat.primes.find((p) => p.saisieId === saisieId);
}

/** Non soumise, ou retenue ou versement sur le net : rangée dans le bloc « Sur le net ». */
export function estSurLeNet(prime: PrimeDuBulletin): boolean {
  return !prime.soumise || Boolean(prime.surLeNet);
}

export function nombreDeChangements(initial: EtatCorrections, courant: EtatCorrections): number {
  const montants = new Map(initial.primes.map((p) => [p.saisieId, p.montant]));
  const primesChangees = courant.primes.filter((p) => montants.has(p.saisieId) && montants.get(p.saisieId) !== p.montant).length;
  const heures =
    courant.hs25 !== initial.hs25 || courant.hs50 !== initial.hs50 || courant.revenirAuPlanning !== initial.revenirAuPlanning ? 1 : 0;
  const complementaires =
    courant.hc1 !== initial.hc1 || courant.hc2 !== initial.hc2 || courant.hcAuPlanning !== initial.hcAuPlanning ? 1 : 0;
  return (
    primesChangees +
    heures +
    complementaires +
    courant.primesRetirees.length +
    courant.primesAjoutees.length +
    courant.correctionsAjoutees.length +
    courant.correctionsRetirees.length +
    courant.regularisationsAjoutees.length +
    courant.regularisationsRetirees.length +
    courant.heuresRegulariseesAjoutees.length +
    courant.heuresRegulariseesRetirees.length
  );
}

export function etapeEnCours(enEdition: boolean, changements: number): 1 | 2 | 3 {
  if (enEdition) return 2;
  return changements > 0 ? 3 : 1;
}
