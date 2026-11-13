/**
 * L'onglet « Corriger » est le bulletin lui-même (design du 11/11/2026,
 * retours de Lyon). Ici, la logique pure : d'où vient une ligne, ce qu'on y
 * corrige, comment elle se retire. Rien n'est calculé ici : toute correction
 * reste une variable du mois, recalculée en entier par Martine.
 */
import type { BlocALaSource, CorrectionLigneAjoutee, LigneCorrigeable } from '@/api/payslips';
import {
  champsDeLaLigne,
  correctionDeLigne,
  TAUX_EN_POURCENT,
  type ChampCorrigeable,
  type ChampDeLigne,
  type DemandeDeCorrection,
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
      return ligne.bloc === 'cotisations' ? 'Le bon montant soumis' : 'Le bon nombre';
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

/**
 * Comment la ligne se retire, ou null : elle se corrige au crayon ou à sa source.
 * Une régularisation ne se retire que si sa saisie est connue du bulletin : un
 * code ancien (au slug) n'aurait rien à envoyer, la poubelle serait sans effet.
 */
export function retraitDeLaLigne(ligne: LigneCorrigeable, etat: EtatCorrections): Retrait | null {
  const origine = origineDeLaLigne(ligne);
  const saisieId = saisieDuCode(ligne.code);
  if (saisieId && origine === 'prime') return { type: origine, saisieId };
  if (saisieId && origine === 'regularisation_heures') {
    return etat.heuresRegularisees.some((h) => h.saisieId === saisieId) ? { type: origine, saisieId } : null;
  }
  if (saisieId && origine === 'regularisation_cotisation') {
    return etat.regularisations.some((r) => r.saisieId === saisieId) ? { type: origine, saisieId } : null;
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

const ajouter = (liste: string[], id: string) => (liste.includes(id) ? liste : [...liste, id]);
const enlever = (liste: string[], id: string) => liste.filter((x) => x !== id);

/** La saisie de la correction déjà posée sur la ligne (au dernier calcul), ou null. */
function correctionPosee(ligne: Pick<LigneCorrigeable, 'correction'>): string | null {
  const id = ligne.correction?.saisie_id;
  return id ? String(id) : null;
}

/**
 * Les reports en cours : la ligne (son code) et la correction non placée
 * qu'elle remplace. Gardés par la page, à côté de l'état : l'onglet
 * « Corriger » est démonté à chaque changement d'onglet, un état local s'y perdait.
 */
export type ReportsDeCorrections = Readonly<Record<string, string>>;

/** Lie (ou délie, avec null) la correction reportée à la ligne. */
export function lierLeReport(reports: ReportsDeCorrections, code: string, id: string | null): ReportsDeCorrections {
  if (id) return reports[code] === id ? reports : { ...reports, [code]: id };
  if (!(code in reports)) return reports;
  const { [code]: _retire, ...reste } = reports;
  return reste;
}

export interface OptionsDeCorrection {
  /** La correction en attente (non placée) que cette correction remplace : « Reporter sur une autre ligne ». */
  reporteDe?: string | null;
  /** Tous les reports en cours : celui de la ligne, et ceux des autres lignes qui retiennent encore la même correction. */
  reports?: ReportsDeCorrections;
  /** La RH avait retiré la correction posée avant d'ouvrir le crayon : l'annulation la laisse retirée. */
  garderLaCorrectionPoseeRetiree?: boolean;
}

/** Une autre ligne, avec sa correction en attente, reporte encore cette correction. */
function encoreReportee(etat: EtatCorrections, code: string, id: string, reports: ReportsDeCorrections | undefined): boolean {
  return Object.entries(reports ?? {}).some(([autre, reporte]) => autre !== code && reporte === id && Boolean(correctionEnAttente(etat, autre)));
}

/**
 * Annule la correction en attente de la ligne, avec ce qu'elle remplaçait :
 * la correction déjà posée sur la ligne et la correction reportée reviennent
 * (sauf si une autre ligne la reporte encore).
 */
export function annulerLaCorrection(
  etat: EtatCorrections,
  ligne: Pick<LigneCorrigeable, 'code' | 'correction'>,
  options: OptionsDeCorrection = {}
): EtatCorrections {
  const code = ligne.code;
  if (!code || !correctionEnAttente(etat, code)) return etat;
  let retirees = etat.correctionsRetirees;
  const posee = correctionPosee(ligne);
  if (posee && !options.garderLaCorrectionPoseeRetiree) retirees = enlever(retirees, posee);
  const reporte = options.reporteDe ?? options.reports?.[code] ?? null;
  if (reporte && !encoreReportee(etat, code, reporte, options.reports)) retirees = enlever(retirees, reporte);
  return {
    ...etat,
    correctionsAjoutees: etat.correctionsAjoutees.filter((c) => c.ligne !== code),
    correctionsRetirees: retirees,
  };
}

/**
 * Pose la correction de la ligne. Une ligne déjà corrigée voit sa correction
 * remplacée (le serveur refuse deux corrections sur la même ligne) : la saisie
 * d'avant part dans les corrections retirées du même enregistrement.
 */
export function corrigerLaLigne(
  etat: EtatCorrections,
  ligne: LigneCorrigeable,
  cle: ChampCorrigeable,
  valeur: number,
  motif: string,
  options: OptionsDeCorrection = {}
): EtatCorrections {
  // Le lien d'avant de la ligne (un autre report) est libéré ; celui-ci est posé ensuite.
  const sans = annulerLaCorrection(etat, ligne, { ...options, reporteDe: options.reports?.[String(ligne.code)] ?? null });
  let retirees = sans.correctionsRetirees;
  const posee = correctionPosee(ligne);
  if (posee) retirees = ajouter(retirees, posee);
  if (options.reporteDe) retirees = ajouter(retirees, options.reporteDe);
  return {
    ...sans,
    correctionsAjoutees: [...sans.correctionsAjoutees, correctionDeLigne(ligne, cle, valeur, motif)],
    correctionsRetirees: retirees,
  };
}

/** Le champ et la valeur d'une correction en attente, dans l'unité de l'écran (taux en %). */
export function valeurEnAttente(
  correction: CorrectionLigneAjoutee | undefined
): { cle: ChampCorrigeable; valeur: number } | null {
  if (!correction) return null;
  const valeurs = correction as unknown as Record<string, unknown>;
  const cle = Object.keys(valeurs).find(
    (k) => !['ligne', 'libelle', 'motif'].includes(k) && typeof valeurs[k] === 'number'
  ) as ChampCorrigeable | undefined;
  if (!cle) return null;
  const brute = valeurs[cle] as number;
  return { cle, valeur: TAUX_EN_POURCENT.has(cle) ? Math.round(brute * 100 * 1e4) / 1e4 : brute };
}

export function estRetiree(etat: EtatCorrections, ligne: LigneCorrigeable): boolean {
  const retrait = retraitDeLaLigne(ligne, etat);
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
  const retrait = retraitDeLaLigne(ligne, etat);
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

export function remettre(
  etat: EtatCorrections,
  ligne: LigneCorrigeable,
  options: Pick<OptionsDeCorrection, 'reports'> = {}
): EtatCorrections {
  const retrait = retraitDeLaLigne(ligne, etat);
  if (!retrait) return etat;
  switch (retrait.type) {
    case 'prime':
      return { ...etat, primesRetirees: enlever(etat.primesRetirees, retrait.saisieId) };
    case 'regularisation_heures':
      return { ...etat, heuresRegulariseesRetirees: enlever(etat.heuresRegulariseesRetirees, retrait.saisieId) };
    case 'regularisation_cotisation':
      return { ...etat, regularisationsRetirees: enlever(etat.regularisationsRetirees, retrait.saisieId) };
    default:
      return annulerLaCorrection(etat, ligne, options);
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
  // Une prime retirée compte une fois, même si son montant avait été changé avant.
  const primesChangees = courant.primes.filter(
    (p) => !courant.primesRetirees.includes(p.saisieId) && montants.has(p.saisieId) && montants.get(p.saisieId) !== p.montant
  ).length;
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

/** Ce qu'une ligne ouverte dit d'elle : en cours, ou une valeur tapée sans motif. */
export type StatutDeLigne = 'edition' | 'sans_motif';

/**
 * Les lignes ouvertes qui comptent pour l'étape 2 : seulement celles sans
 * correction en attente (une valeur et un motif font l'étape 3, « Appliquez »).
 */
export function suiviDesLignes(
  statuts: ReadonlyMap<string, StatutDeLigne>,
  etat: EtatCorrections
): { enEdition: number; sansMotif: number } {
  let enEdition = 0;
  let sansMotif = 0;
  for (const [code, statut] of statuts) {
    if (correctionEnAttente(etat, code)) continue;
    enEdition += 1;
    if (statut === 'sans_motif') sansMotif += 1;
  }
  return { enEdition, sansMotif };
}

const centimes = (x: number) => Math.round(Math.abs(x) * 100);

/**
 * Les montants sur le net qui ne sont pas déjà montrés comme primes. La
 * comparaison se fait aux primes du serveur (état initial) : un montant en
 * cours de modification faisait sinon réapparaître la prime en double.
 */
export function autresMontantsDuNet(aLaSource: BlocALaSource[], initial: EtatCorrections): BlocALaSource[] {
  return aLaSource.filter(
    (b) => !initial.primes.some((p) => p.libelle === b.libelle && b.montant != null && centimes(p.montant) === centimes(b.montant))
  );
}

/**
 * Le bloc replié des cotisations s'ouvre quand une cotisation y demande
 * l'attention : en cours, en alerte, visée par l'onglet « Bulletin », ou changée.
 */
export function cotisationsAOuvrir(
  cotisations: LigneCorrigeable[],
  etat: EtatCorrections,
  statuts: ReadonlyMap<string, StatutDeLigne>,
  demande: DemandeDeCorrection | null | undefined
): boolean {
  return cotisations.some(
    (l) =>
      (l.code != null && statuts.has(l.code)) ||
      Boolean(l.alerte) ||
      (demande?.carte === 'ligne' && demande.code === l.code) ||
      Boolean(correctionEnAttente(etat, l.code)) ||
      estRetiree(etat, l)
  );
}

/**
 * La version à remettre par « Annuler » : la dernière de l'historique, à
 * condition qu'elle soit celle de cette application (même numéro, même net
 * d'avant quand l'historique le porte). Sinon null : la RH choisit dans
 * l'onglet « Historique ».
 */
export function versionAAnnuler(
  versions: ReadonlyArray<{ version: number; previous_payslip_data?: unknown }>,
  attendu: { version: number | null; netAvant: number | null }
): number | null {
  if (versions.length === 0) return null;
  const derniere = versions.reduce((max, v) => (v.version > max.version ? v : max));
  if (!derniere.version) return null;
  if (attendu.version != null && derniere.version !== attendu.version) return null;
  const netArchive = (derniere.previous_payslip_data as { net_a_payer?: unknown } | null | undefined)?.net_a_payer;
  if (attendu.netAvant != null && typeof netArchive === 'number' && Math.round(netArchive * 100) !== Math.round(attendu.netAvant * 100)) {
    return null;
  }
  return derniere.version;
}
