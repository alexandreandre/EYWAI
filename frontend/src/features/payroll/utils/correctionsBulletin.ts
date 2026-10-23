/**
 * Corriger un bulletin par ses variables du mois (audit du 28/09).
 *
 * L'écran n'envoie plus le bulletin retouché : les montants retouchés à la main
 * laissaient cotisations, net et cumuls de l'ancien calcul. Il envoie des
 * corrections — heures sup par palier, primes saisies du mois, notes — que le
 * serveur écrit comme variables du mois avant de recalculer tout le bulletin.
 *
 * La lecture des heures sup suit celle du serveur
 * (`backend/app/modules/payslips/domain/heures_sup.py`) : lignes « Heures
 * suppl. » hors structurelles, palier lu sur le taux. Les primes sont les
 * lignes imprimées depuis une saisie (`saisie_id`), comme
 * `domain/primes_editees.py`.
 */
import type { CorrectionLigneAjoutee, LigneCorrigeable, PayslipEditRequest, PrimeAjoutee, RegularisationAjoutee } from '@/api/payslips';
import type { MonthlyInputCreate } from '@/api/saisies';
import { deDevant } from './elision';
import { monthLabel } from './payrollMonth';
import { estLigneHeuresSupConjoncturelle } from './payslipDerivedLines';

const TOLERANCE = 0.005;
const SECTIONS_PRIMES = ['calcul_du_brut', 'primes_non_soumises'] as const;

export interface PrimeDuBulletin {
  saisieId: string;
  libelle: string;
  montant: number;
  /** Imprimée dans le brut (soumise à cotisations) ou parmi les non soumises. */
  soumise: boolean;
  /** Saisie qui ne touche que le net à payer : retenue (montant négatif) ou versement. */
  surLeNet?: 'retenue' | 'versement';
}

/** Une saisie du mois telle que l'API la renvoie (seuls les champs lus ici). */
export interface SaisieDuMois {
  id: string;
  name: string;
  amount: number;
  sur_le_net?: boolean | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Une saisie du mois enregistrée après le dernier calcul : pas encore sur le bulletin. */
export interface SaisieApresCalcul {
  saisieId: string;
  libelle: string;
  montant: number;
}

/** Le bulletin ne porte aucune prime : il ne dit rien des saisies d'après son calcul. */
export const MESSAGE_AUCUNE_PRIME = 'Aucune prime sur ce bulletin.';

const HEURES_CORRIGEES_AU_BULLETIN = /\(corrigées au bulletin\)$/;

function instant(texte: string | null | undefined): number | null {
  if (!texte) return null;
  const t = Date.parse(texte);
  return Number.isFinite(t) ? t : null;
}

/**
 * Les saisies du mois enregistrées (ou modifiées) après le dernier calcul.
 *
 * L'onglet lit les primes sur les lignes du bulletin : une prime de 300 €
 * saisie après coup n'y était pas, et l'écran disait « Aucune prime saisie
 * pour ce mois » (relevé J.1). Elles sont montrées à part, jusqu'au recalcul.
 * Les heures sup corrigées depuis le bulletin ont leur propre carte. Sans date
 * de calcul, rien n'est deviné.
 */
export function saisiesApresLeCalcul(
  saisies: SaisieDuMois[],
  calculeLe: string | null | undefined,
  etat: EtatCorrections
): SaisieApresCalcul[] {
  const calcul = instant(calculeLe);
  if (calcul === null) return [];
  const connues = new Set(etat.primes.map((p) => p.saisieId));
  return saisies
    .filter((s) => !connues.has(String(s.id)))
    .filter((s) => !HEURES_CORRIGEES_AU_BULLETIN.test(s.name ?? ''))
    .filter((s) => {
      const depuis = Math.max(instant(s.created_at) ?? -Infinity, instant(s.updated_at) ?? -Infinity);
      return depuis > calcul;
    })
    .map((s) => ({
      saisieId: String(s.id),
      libelle: s.name || 'Saisie du mois',
      montant: arrondi(nombre(s.amount) ?? 0),
    }));
}

export interface EtatCorrections {
  hs25: number;
  hs50: number;
  revenirAuPlanning: boolean;
  primes: PrimeDuBulletin[];
  primesRetirees: string[];
  primesAjoutees: PrimeAjoutee[];
  regularisations: RegularisationDuBulletin[];
  regularisationsAjoutees: RegularisationAjoutee[];
  regularisationsRetirees: string[];
  correctionsAjoutees: CorrectionLigneAjoutee[];
  correctionsRetirees: string[];
  pdfNotes: string;
  noteInterne: string;
  resume: string;
}

export interface HeuresDeclarees {
  hs25: number;
  hs50: number;
  planning: number;
}

type Ligne = Record<string, unknown>;

function arrondi(valeur: number): number {
  return Math.round(valeur * 100) / 100;
}

function nombre(valeur: unknown): number | null {
  return typeof valeur === 'number' && Number.isFinite(valeur) ? valeur : null;
}

function lignesDe(data: unknown, section: string): Ligne[] {
  const d = (data ?? {}) as Record<string, unknown>;
  const lignes = d[section];
  return Array.isArray(lignes)
    ? (lignes as Ligne[]).filter((l) => l && typeof l === 'object' && !l.is_sous_total)
    : [];
}

/** (premier palier, second palier) imprimés sur le bulletin. */
export function quantitesHeuresSup(data: unknown): [number, number] {
  const retenues: Array<[number, number, string]> = [];
  for (const ligne of lignesDe(data, 'calcul_du_brut')) {
    const libelle = typeof ligne.libelle === 'string' ? ligne.libelle : '';
    if (!estLigneHeuresSupConjoncturelle(libelle)) continue;
    const quantite = nombre(ligne.quantite);
    if (quantite === null) return [0, 0];
    retenues.push([nombre(ligne.taux) ?? 0, quantite, libelle]);
  }
  if (retenues.length === 0) return [0, 0];
  retenues.sort((a, b) => a[0] - b[0]);
  if (retenues.length === 1) {
    const [, quantite, libelle] = retenues[0];
    return libelle.includes('50') ? [0, arrondi(quantite)] : [arrondi(quantite), 0];
  }
  const premier = retenues.slice(0, -1).reduce((total, [, q]) => total + q, 0);
  return [arrondi(premier), arrondi(retenues[retenues.length - 1][1])];
}

/** Les heures déclarées au bulletin, quand le moteur les a fait primer. */
export function heuresDeclarees(data: unknown): HeuresDeclarees | null {
  const d = (data ?? {}) as { heures_sup_declarees?: unknown };
  const h = d.heures_sup_declarees as Record<string, unknown> | undefined;
  if (!h || typeof h !== 'object') return null;
  return {
    hs25: nombre(h.hs25) ?? 0,
    hs50: nombre(h.hs50) ?? 0,
    planning: nombre(h.planning) ?? 0,
  };
}

const HEURES_STRUCTURELLES = /^heures suppl\.? structurelles/i;

function heuresFr(valeur: number): string {
  return `${arrondi(valeur)}`.replace('.', ',');
}

/**
 * Ce que la carte « Heures supplémentaires du mois » dit des heures déclarées.
 *
 * Le moteur ne remplace que les heures au-delà de l'horaire du contrat (celles
 * que donne le planning) ; les heures structurelles d'un contrat à 39 h sont
 * payées chaque mois et restent. Pour un 39 h, 20 h déclarées faisaient lire
 * « 17,33 h → 37,33 h » sous une carte qui disait seulement « elles
 * remplacent » (relevé J.1) : la phrase nomme les structurelles qui restent.
 */
export function descriptionHeuresSupDuMois(data: unknown): string {
  const structurelles = lignesDe(data, 'calcul_du_brut')
    .filter((l) => typeof l.libelle === 'string' && HEURES_STRUCTURELLES.test(l.libelle))
    .reduce((total, l) => total + (nombre(l.quantite) ?? 0), 0);
  const phrases = [
    'Les heures au-delà de l’horaire du contrat. Déclarées ici, elles remplacent celles du planning pour ce bulletin, même à zéro.',
  ];
  if (structurelles > 0) {
    phrases.push(`Les ${heuresFr(structurelles)} h structurelles du contrat restent payées en plus.`);
  }
  phrases.push('À l’enregistrement, le bulletin est recalculé en entier.');
  return phrases.join(' ');
}

export function primesDuBulletin(data: unknown): PrimeDuBulletin[] {
  return SECTIONS_PRIMES.flatMap((section) =>
    lignesDe(data, section)
      .filter((l) => l.saisie_id)
      .map((l) => ({
        saisieId: String(l.saisie_id),
        libelle: typeof l.libelle === 'string' && l.libelle ? l.libelle : 'Prime',
        montant: arrondi(nombre(l.gain) ?? nombre(l.montant) ?? 0),
        soumise: section === 'calcul_du_brut',
      }))
  );
}

/**
 * Montant d'une prime après correction : le sens (retenue, versement, prime)
 * ne change jamais en corrigeant, quel que soit le signe tapé.
 */
export function montantCorrigeDeLaPrime(prime: PrimeDuBulletin, saisi: number): number {
  if (prime.surLeNet === 'retenue') return -Math.abs(saisi);
  if (prime.surLeNet === 'versement') return Math.abs(saisi);
  return saisi;
}

/**
 * Les retenues et versements sur le net ne sont pas imprimés comme des lignes
 * de prime : le bulletin ne les porte pas. On les lit dans les saisies du mois
 * et on les ajoute aux primes, corrigeables et retirables comme elles.
 */
export function avecSaisiesSurLeNet(etat: EtatCorrections, saisies: SaisieDuMois[]): EtatCorrections {
  const connues = new Set(etat.primes.map((p) => p.saisieId));
  const nouvelles: PrimeDuBulletin[] = saisies
    .filter((s) => s.sur_le_net && !connues.has(String(s.id)))
    .map((s) => {
      const montant = arrondi(nombre(s.amount) ?? 0);
      return {
        saisieId: String(s.id),
        libelle: s.name || 'Saisie sur le net',
        montant,
        soumise: false,
        surLeNet: montant < 0 ? ('retenue' as const) : ('versement' as const),
      };
    });
  return nouvelles.length ? { ...etat, primes: [...etat.primes, ...nouvelles] } : etat;
}

/** Une prime choisie dans le sélecteur des primes, prête à être ajoutée au mois. */
export function primeDepuisSaisie(saisie: MonthlyInputCreate): PrimeAjoutee {
  return {
    name: saisie.name,
    amount: arrondi(Number(saisie.amount) || 0),
    is_socially_taxed: saisie.is_socially_taxed ?? true,
    is_taxable: saisie.is_taxable ?? true,
    sur_le_net: saisie.sur_le_net ?? false,
    catalog_prime_id: saisie.catalog_prime_id ?? null,
  };
}

/** Une cotisation du bulletin qu'on peut régulariser (elle porte un organisme). */
export interface CotisationRegularisable {
  cotiId: string;
  libelle: string;
  tauxSalarial: number | null;
  tauxPatronal: number | null;
}

/** Une régularisation imprimée sur le bulletin. */
export interface RegularisationDuBulletin {
  saisieId: string;
  libelle: string;
  motif: string;
  montantSalarial: number;
  montantPatronal: number;
}

function lignesDeCotisation(data: unknown): Ligne[] {
  const d = (data ?? {}) as { cotisations_officielles?: unknown };
  const rubriques = Array.isArray(d.cotisations_officielles) ? (d.cotisations_officielles as Ligne[]) : [];
  return rubriques.flatMap((r) => (Array.isArray(r.lignes) ? (r.lignes as Ligne[]) : []));
}

export function cotisationsRegularisables(data: unknown): CotisationRegularisable[] {
  const vues = new Set<string>();
  const sortie: CotisationRegularisable[] = [];
  for (const l of lignesDeCotisation(data)) {
    if (!l.coti_id || l.regularisation || l.is_participation || l.is_ppv) continue;
    const libelle = typeof l.libelle === 'string' ? l.libelle : String(l.coti_id);
    const cle = `${l.coti_id}|${libelle}`;
    if (vues.has(cle)) continue;
    vues.add(cle);
    sortie.push({
      cotiId: String(l.coti_id),
      libelle,
      tauxSalarial: nombre(l.taux_salarial) || null,
      tauxPatronal: nombre(l.taux_patronal) || null,
    });
  }
  return sortie;
}

export function regularisationsDuBulletin(data: unknown): RegularisationDuBulletin[] {
  return lignesDeCotisation(data)
    .filter((l) => {
      const charge = l.regularisation as Ligne | undefined;
      return !!charge && typeof charge === 'object' && !!charge.saisie_id;
    })
    .map((l) => {
      const charge = l.regularisation as Ligne;
      // Le montant juste est celui de la ligne recalculée. La charge utile
      // peut le laisser vide : c'est la base et le taux qui ont été saisis.
      const salarial = nombre(l.montant_salarial) ?? nombre(charge.montant_salarial) ?? 0;
      const patronal = nombre(l.montant_patronal) ?? nombre(charge.montant_patronal) ?? 0;
      return {
        saisieId: String(charge.saisie_id),
        libelle: String(charge.libelle ?? ''),
        motif: String(charge.motif ?? ''),
        montantSalarial: arrondi(salarial),
        montantPatronal: arrondi(patronal),
      };
    });
}

export type PartRegularisee = 'salariale' | 'patronale' | 'les_deux';

/**
 * Un écart en euros devient une base au taux de la cotisation. Le serveur
 * recalcule le montant arrondi. Sans taux, l'écart est le montant.
 */
export function regularisationDepuisEcart(
  cotisation: CotisationRegularisable,
  ecart: number,
  part: PartRegularisee,
  motif: string
): RegularisationAjoutee {
  const tauxSal = part === 'patronale' ? null : cotisation.tauxSalarial;
  const tauxPat = part === 'salariale' ? null : cotisation.tauxPatronal;
  const taux = (tauxSal ?? 0) + (tauxPat ?? 0);
  const commun = { coti_id: cotisation.cotiId, libelle: cotisation.libelle, motif: motif.trim() };
  if (taux) {
    return { ...commun, base: arrondi(ecart / taux), taux_salarial: tauxSal, taux_patronal: tauxPat };
  }
  return {
    ...commun,
    montant_salarial: part === 'patronale' ? null : arrondi(ecart),
    montant_patronal: part === 'patronale' ? arrondi(ecart) : null,
  };
}

export function etatInitial(data: unknown, pdfNotes: string | null | undefined): EtatCorrections {
  const [hs25, hs50] = quantitesHeuresSup(data);
  return {
    hs25,
    hs50,
    revenirAuPlanning: false,
    primes: primesDuBulletin(data),
    primesRetirees: [],
    primesAjoutees: [],
    regularisations: regularisationsDuBulletin(data),
    regularisationsAjoutees: [],
    regularisationsRetirees: [],
    correctionsAjoutees: [],
    correctionsRetirees: [],
    pdfNotes: pdfNotes ?? '',
    noteInterne: '',
    resume: '',
  };
}

function proches(a: number, b: number): boolean {
  return Math.abs(a - b) <= TOLERANCE;
}

export function requeteDeCorrection(
  initial: EtatCorrections,
  courant: EtatCorrections,
  baseUpdatedAt: string | null | undefined
): PayslipEditRequest {
  const montantsInitiaux = new Map(initial.primes.map((p) => [p.saisieId, p.montant]));
  const retirees = new Set(courant.primesRetirees);
  const heuresChangees =
    !proches(courant.hs25, initial.hs25) || !proches(courant.hs50, initial.hs50);

  const corrections: PayslipEditRequest['corrections'] = {};
  if (courant.revenirAuPlanning) {
    corrections.revenir_au_planning = true;
  } else if (heuresChangees) {
    corrections.heures_sup = { hs25: arrondi(courant.hs25), hs50: arrondi(courant.hs50) };
  }
  const corrigees = courant.primes
    .filter((p) => !retirees.has(p.saisieId))
    .filter((p) => {
      const avant = montantsInitiaux.get(p.saisieId);
      return avant !== undefined && !proches(avant, p.montant);
    })
    .map((p) => ({ saisie_id: p.saisieId, amount: arrondi(p.montant) }));
  if (corrigees.length) corrections.primes_corrigees = corrigees;
  if (retirees.size) corrections.primes_retirees = [...retirees];
  if (courant.primesAjoutees.length) {
    corrections.primes_ajoutees = courant.primesAjoutees.map((p) => ({
      ...p,
      amount: arrondi(p.amount),
    }));
  }
  if (courant.regularisationsAjoutees.length) corrections.regularisations_ajoutees = courant.regularisationsAjoutees;
  if (courant.regularisationsRetirees.length) corrections.regularisations_retirees = courant.regularisationsRetirees;
  if (courant.correctionsAjoutees.length) corrections.corrections_ajoutees = courant.correctionsAjoutees;
  if (courant.correctionsRetirees.length) corrections.corrections_retirees = courant.correctionsRetirees;

  const requete: PayslipEditRequest = { corrections };
  if (courant.pdfNotes.trim() !== initial.pdfNotes.trim()) requete.pdf_notes = courant.pdfNotes;
  if (courant.noteInterne.trim()) requete.internal_note = courant.noteInterne.trim();
  if (courant.resume.trim()) requete.changes_summary = courant.resume.trim();
  if (baseUpdatedAt) requete.base_updated_at = baseUpdatedAt;
  return requete;
}

/** Quelque chose à enregistrer : une variable, la note du PDF ou une note interne. */
export function aDesModifications(initial: EtatCorrections, courant: EtatCorrections): boolean {
  const requete = requeteDeCorrection(initial, courant, null);
  return (
    Object.keys(requete.corrections).length > 0 ||
    requete.pdf_notes !== undefined ||
    requete.internal_note !== undefined
  );
}

/** Les variables changent : le serveur recalculera le bulletin. */
export function recalculAttendu(initial: EtatCorrections, courant: EtatCorrections): boolean {
  return Object.keys(requeteDeCorrection(initial, courant, null).corrections).length > 0;
}

/**
 * Un bulletin validé repasse en brouillon si le document remis change : une
 * variable (donc un montant) ou la note du PDF. Une note interne seule le
 * laisse validé [J1].
 */
export function repasseEnBrouillon(initial: EtatCorrections, courant: EtatCorrections): boolean {
  const requete = requeteDeCorrection(initial, courant, null);
  return Object.keys(requete.corrections).length > 0 || requete.pdf_notes !== undefined;
}

/** « Bulletin d'octobre 2026 — Camille Roussel » : le mois et le salarié, jamais le nom du fichier. */
export function titreDuBulletin(payslipData: unknown, month: number, year: number): string {
  const salarie = (payslipData as { en_tete?: { salarie?: Record<string, unknown> } } | null | undefined)
    ?.en_tete?.salarie;
  const texte = (v: unknown) => (typeof v === 'string' ? v.trim() : '');
  const nom =
    texte(salarie?.nom_complet) || [texte(salarie?.prenom), texte(salarie?.nom)].filter(Boolean).join(' ');
  const debut = `Bulletin ${deDevant(monthLabel(month).toLowerCase())} ${year}`;
  return nom ? `${debut} — ${nom}` : debut;
}

/** Ce qui se tape pour corriger une ligne, selon la règle 3. */
export type ChampCorrigeable =
  | 'base'
  | 'taux'
  | 'montant'
  | 'taux_salarial'
  | 'taux_patronal'
  | 'montant_salarial'
  | 'montant_patronal';

export interface ChampDeLigne {
  cle: ChampCorrigeable;
  libelle: string;
  /** La valeur de Martine, dans l'unité tapée (un taux de cotisation en %). */
  valeur: number | null;
}

const TAUX_EN_POURCENT: ReadonlySet<ChampCorrigeable> = new Set<ChampCorrigeable>(['taux_salarial', 'taux_patronal']);

function pourcent(fraction: number | null | undefined): number | null {
  return typeof fraction === 'number' ? Math.round(fraction * 1e6) / 1e4 : null;
}

/** Les champs que la ligne laisse corriger. Rien pour une ligne qui ne se corrige pas ici. */
export function champsDeLaLigne(ligne: LigneCorrigeable): ChampDeLigne[] {
  if (!ligne.mode) return [];
  if (ligne.bloc === 'impot') {
    return [{ cle: 'taux', libelle: 'Taux d’impôt du mois (%)', valeur: ligne.taux ?? null }];
  }
  if (ligne.bloc === 'brut') {
    if (ligne.mode === 'base_ou_taux') {
      return [
        { cle: 'base', libelle: 'Base (heures, jours ou quantité)', valeur: ligne.base ?? null },
        { cle: 'taux', libelle: 'Taux', valeur: ligne.taux ?? null },
      ];
    }
    return [{ cle: 'montant', libelle: ligne.retenue ? 'Retenue (€)' : 'Montant (€)', valeur: ligne.montant ?? null }];
  }
  if (ligne.mode === 'base_ou_taux') {
    const champs: ChampDeLigne[] = [{ cle: 'base', libelle: 'Base (€)', valeur: ligne.base ?? null }];
    if (ligne.taux_salarial != null) {
      champs.push({ cle: 'taux_salarial', libelle: 'Taux salarial (%)', valeur: pourcent(ligne.taux_salarial) });
    }
    if (ligne.taux_patronal != null) {
      champs.push({ cle: 'taux_patronal', libelle: 'Taux patronal (%)', valeur: pourcent(ligne.taux_patronal) });
    }
    return champs;
  }
  return [
    { cle: 'montant_salarial', libelle: 'Part salariale (€)', valeur: ligne.montant_salarial ?? null },
    { cle: 'montant_patronal', libelle: 'Part patronale (€)', valeur: ligne.montant_patronal ?? null },
  ];
}

/** La correction à envoyer : un seul champ, un taux de cotisation repassé en fraction. */
export function correctionDeLigne(
  ligne: LigneCorrigeable,
  cle: ChampCorrigeable,
  saisie: number,
  motif: string
): CorrectionLigneAjoutee {
  const correction: CorrectionLigneAjoutee = { ligne: String(ligne.code), libelle: ligne.libelle, motif: motif.trim() };
  correction[cle] = TAUX_EN_POURCENT.has(cle) ? Math.round(saisie * 1e4) / 1e6 : saisie;
  return correction;
}

/** Le montant qu'aura la ligne, pour l'aperçu. Le serveur le recalcule. */
export function apercuDuMontant(ligne: LigneCorrigeable, cle: ChampCorrigeable, saisie: number): number | null {
  if (!Number.isFinite(saisie)) return null;
  if (ligne.bloc === 'impot') return ligne.base != null ? arrondi((ligne.base * saisie) / 100) : null;
  if (cle === 'montant' || cle === 'montant_salarial' || cle === 'montant_patronal') return arrondi(saisie);
  const base = cle === 'base' ? saisie : ligne.base ?? 0;
  if (ligne.bloc === 'brut') return arrondi(base * (cle === 'taux' ? saisie : ligne.taux ?? 0));
  const salarial = cle === 'taux_salarial' ? saisie / 100 : ligne.taux_salarial ?? 0;
  const patronal = cle === 'taux_patronal' ? saisie / 100 : ligne.taux_patronal ?? 0;
  return arrondi(arrondi(base * salarial) + arrondi(base * patronal));
}

/** « 1 234,50 € », avec des espaces ordinaires (les espaces insécables du navigateur varient). */
export function eurosFr(valeur: number): string {
  const [entier, decimales] = Math.abs(valeur).toFixed(2).split('.');
  return `${valeur < 0 ? '−' : ''}${entier.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')},${decimales} €`;
}

function tauxFr(valeur: number): string {
  return `${valeur.toFixed(2).replace('.', ',')} %`;
}

/** « Martine : 2 500,00 € → corrigé : 2 637,31 € ». */
export function resumeDeLaCorrection(ligne: LigneCorrigeable): string {
  const calcule = (ligne.valeur_calculee ?? {}) as Record<string, number | null | undefined>;
  if (ligne.bloc === 'impot') {
    return `Martine : ${tauxFr(calcule.taux ?? 0)} → corrigé : ${tauxFr(ligne.taux ?? 0)}`;
  }
  if (ligne.bloc === 'brut') {
    return `Martine : ${eurosFr(calcule.gain ?? calcule.perte ?? 0)} → corrigé : ${eurosFr(ligne.montant ?? 0)}`;
  }
  const avant = arrondi((calcule.montant_salarial ?? 0) + (calcule.montant_patronal ?? 0));
  const apres = arrondi((ligne.montant_salarial ?? 0) + (ligne.montant_patronal ?? 0));
  return `Martine : ${eurosFr(avant)} → corrigé : ${eurosFr(apres)}`;
}
