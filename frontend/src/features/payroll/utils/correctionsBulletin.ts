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
import type {
  CorrectionLigneAjoutee,
  LigneCorrigeable,
  NatureHeuresRegularisees,
  PayslipEditRequest,
  PrimeAjoutee,
  RegularisationAjoutee,
  RegularisationHeuresAjoutee,
} from '@/api/payslips';
import type { MonthlyInputCreate } from '@/api/saisies';
import { lireNombre } from '@/lib/nombreSaisi';
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
  /** Heures complémentaires d'un temps partiel, au premier et au second palier. */
  hc1: number;
  hc2: number;
  hcAuPlanning: boolean;
  primes: PrimeDuBulletin[];
  primesRetirees: string[];
  primesAjoutees: PrimeAjoutee[];
  regularisations: RegularisationDuBulletin[];
  regularisationsAjoutees: RegularisationAjoutee[];
  regularisationsRetirees: string[];
  heuresRegularisees: HeuresRegulariseesDuBulletin[];
  heuresRegulariseesAjoutees: RegularisationHeuresAjoutee[];
  heuresRegulariseesRetirees: string[];
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

/** La valeur que Martine avait calculée pour une ligne corrigée à la main ; la ligne elle-même sinon. */
function avantLaCorrection(ligne: Ligne): Ligne {
  const calcule = ligne.valeur_calculee;
  return ligne.correction && calcule && typeof calcule === 'object' ? { ...ligne, ...(calcule as Ligne) } : ligne;
}

/**
 * (premier palier, second palier) imprimés sur le bulletin.
 *
 * Une ligne corrigée à la main compte pour la quantité que Martine avait
 * calculée : la carte « Heures supplémentaires du mois » reprenait sinon les
 * 8 h de la correction pour 5 h déclarées, et retoucher l'autre palier les
 * déclarait (jeu du 23/10).
 */
export function quantitesHeuresSup(data: unknown): [number, number] {
  const retenues: Array<[number, number, string]> = [];
  for (const imprimee of lignesDe(data, 'calcul_du_brut')) {
    const ligne = avantLaCorrection(imprimee);
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

const HEURES_COMPLEMENTAIRES = /^Heures complémentaires majorées à (\d+(?:[.,]\d+)?)\s*%/;

/** Les majorations (en %) des deux paliers d'heures complémentaires : celles du bulletin, sinon 10 et 25 (C. trav. L3123-29). */
export function paliersHeuresComplementaires(data: unknown): [number, number] {
  const lus = lignesDe(data, 'calcul_du_brut')
    .map((l) => (typeof l.libelle === 'string' ? HEURES_COMPLEMENTAIRES.exec(l.libelle) : null))
    .filter((m): m is RegExpExecArray => !!m)
    .map((m) => lireNombre(m[1]) ?? 0)
    .sort((a, b) => a - b);
  const uniques = [...new Set(lus)];
  if (uniques.length >= 2) return [uniques[0], uniques[uniques.length - 1]];
  if (uniques.length === 1) return uniques[0] >= 25 ? [10, uniques[0]] : [uniques[0], 25];
  return [10, 25];
}

/** (premier palier, second palier) des heures complémentaires : déclarées, sinon imprimées. */
export function quantitesHeuresComplementaires(data: unknown): [number, number] {
  const d = (data ?? {}) as { heures_complementaires_declarees?: unknown };
  const declarees = d.heures_complementaires_declarees as Record<string, unknown> | undefined;
  if (declarees && typeof declarees === 'object') {
    return [nombre(declarees.hc1) ?? 0, nombre(declarees.hc2) ?? 0];
  }
  const [premier] = paliersHeuresComplementaires(data);
  let hc1 = 0;
  let hc2 = 0;
  for (const imprimee of lignesDe(data, 'calcul_du_brut')) {
    const ligne = avantLaCorrection(imprimee);
    const m = typeof ligne.libelle === 'string' ? HEURES_COMPLEMENTAIRES.exec(ligne.libelle) : null;
    if (!m) continue;
    const quantite = nombre(ligne.quantite) ?? 0;
    if ((lireNombre(m[1]) ?? 0) <= premier) hc1 += quantite;
    else hc2 += quantite;
  }
  return [arrondi(hc1), arrondi(hc2)];
}

/** Les heures complémentaires déclarées au bulletin, quand le moteur les a fait primer. */
export function heuresComplementairesDeclarees(data: unknown): HeuresDeclarees | null {
  const d = (data ?? {}) as { heures_complementaires_declarees?: unknown };
  const h = d.heures_complementaires_declarees as Record<string, unknown> | undefined;
  if (!h || typeof h !== 'object') return null;
  return { hs25: nombre(h.hc1) ?? 0, hs50: nombre(h.hc2) ?? 0, planning: nombre(h.planning) ?? 0 };
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

/**
 * La CSG et le forfait social de la participation ou de la PPV n'ont pas
 * d'organisme : le libellé le donne, c'est lui que la DSN traduira.
 */
function cotiIdHorsSalaire(l: Ligne): string | null {
  if (!(l.is_participation || l.is_ppv)) return null;
  const libelle = String(l.libelle ?? '').toLowerCase();
  if (libelle.startsWith('csg déductible')) return 'csg_deductible';
  if (libelle.startsWith('csg/crds non déductible')) return 'csg_non_deductible';
  if (libelle.startsWith('forfait social')) return 'forfait_social';
  return null;
}

export function cotisationsRegularisables(data: unknown): CotisationRegularisable[] {
  const vues = new Set<string>();
  const sortie: CotisationRegularisable[] = [];
  for (const l of lignesDeCotisation(data)) {
    if (l.regularisation) continue;
    const cotiId = l.is_participation || l.is_ppv ? cotiIdHorsSalaire(l) : (l.coti_id ? String(l.coti_id) : null);
    if (!cotiId) continue;
    const libelle = typeof l.libelle === 'string' ? l.libelle : cotiId;
    const cle = `${cotiId}|${libelle}`;
    if (vues.has(cle)) continue;
    vues.add(cle);
    sortie.push({
      cotiId,
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

/** Des heures d'un autre mois imprimées sur le bulletin. */
export interface HeuresRegulariseesDuBulletin {
  saisieId: string;
  libelle: string;
  motif: string;
  quantite: number;
  taux: number;
  montant: number;
}

export function heuresRegulariseesDuBulletin(data: unknown): HeuresRegulariseesDuBulletin[] {
  const brut = (data as { calcul_du_brut?: unknown } | null | undefined)?.calcul_du_brut;
  if (!Array.isArray(brut)) return [];
  return brut
    .filter((l): l is Ligne => !!l && typeof l === 'object')
    .filter((l) => {
      const charge = l.regularisation_heures as Ligne | undefined;
      return !!charge && typeof charge === 'object' && !!charge.saisie_id;
    })
    .map((l) => {
      const charge = l.regularisation_heures as Ligne;
      return {
        saisieId: String(charge.saisie_id),
        libelle: String(l.libelle ?? ''),
        motif: String(charge.motif ?? ''),
        quantite: nombre(l.quantite) ?? 0,
        taux: nombre(l.taux) ?? 0,
        montant: arrondi(nombre(l.gain) ?? 0),
      };
    });
}

export const NATURES_HEURES_REGULARISEES: Array<{ valeur: NatureHeuresRegularisees; libelle: string }> = [
  { valeur: 'hs1', libelle: 'Heures sup, 1er palier (25 % en général)' },
  { valeur: 'hs2', libelle: 'Heures sup, 2d palier (50 % en général)' },
  { valeur: 'normales', libelle: 'Heures au taux normal' },
  { valeur: 'hc1', libelle: 'Heures complémentaires, 1er palier (10 %)' },
  { valeur: 'hc2', libelle: 'Heures complémentaires, 2d palier (25 %)' },
];

/** « 2026-09 » → « 09/2026 ». */
export function moisAffiche(mois: string): string {
  const [annee, m] = mois.split('-');
  return annee && m ? `${m}/${annee}` : mois;
}

/** Le mois précédant celui du bulletin, au format « AAAA-MM ». */
export function moisPrecedent(year: number, month: number): string {
  const y = month === 1 ? year - 1 : year;
  const m = month === 1 ? 12 : month - 1;
  return `${y}-${String(m).padStart(2, '0')}`;
}

export type PartRegularisee = 'salariale' | 'patronale' | 'les_deux';

/** Les mois (« AAAA-MM ») qu'une régularisation corrige. */
export interface PeriodeRegularisee {
  debut: string;
  fin: string;
}

const MOIS = /^\d{4}-(0[1-9]|1[0-2])$/;

/** Une période lisible, dans l'ordre, qui ne dépasse pas le mois du bulletin. */
export function periodeValide(periode: PeriodeRegularisee, moisMax: string): boolean {
  return MOIS.test(periode.debut) && MOIS.test(periode.fin) && periode.debut <= periode.fin && periode.fin <= moisMax;
}

/** « 09/2026 », ou « 07/2026 à 09/2026 ». */
export function periodeAffichee(debut: string, fin?: string | null): string {
  return !fin || fin === debut ? moisAffiche(debut) : `${moisAffiche(debut)} à ${moisAffiche(fin)}`;
}

/**
 * Un écart en euros devient une base au taux de la cotisation. Le serveur
 * recalcule le montant arrondi. Sans taux, l'écart est le montant.
 */
export function regularisationDepuisEcart(
  cotisation: CotisationRegularisable,
  ecart: number,
  part: PartRegularisee,
  motif: string,
  periode?: PeriodeRegularisee | null
): RegularisationAjoutee {
  const tauxSal = part === 'patronale' ? null : cotisation.tauxSalarial;
  const tauxPat = part === 'salariale' ? null : cotisation.tauxPatronal;
  const taux = (tauxSal ?? 0) + (tauxPat ?? 0);
  const commun = {
    coti_id: cotisation.cotiId,
    libelle: cotisation.libelle,
    motif: motif.trim(),
    ...(periode ? { mois_debut: periode.debut, mois_fin: periode.fin } : {}),
  };
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
  // Les heures déclarées au bulletin (les variables du mois) font foi, jamais
  // la quantité d'une ligne corrigée à la main.
  const declarees = heuresDeclarees(data);
  const [hs25, hs50] = declarees ? [declarees.hs25, declarees.hs50] : quantitesHeuresSup(data);
  const [hc1, hc2] = quantitesHeuresComplementaires(data);
  return {
    hs25,
    hs50,
    revenirAuPlanning: false,
    hc1,
    hc2,
    hcAuPlanning: false,
    primes: primesDuBulletin(data),
    primesRetirees: [],
    primesAjoutees: [],
    regularisations: regularisationsDuBulletin(data),
    regularisationsAjoutees: [],
    regularisationsRetirees: [],
    heuresRegularisees: heuresRegulariseesDuBulletin(data),
    heuresRegulariseesAjoutees: [],
    heuresRegulariseesRetirees: [],
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
  if (courant.hcAuPlanning) {
    corrections.heures_complementaires_au_planning = true;
  } else if (!proches(courant.hc1, initial.hc1) || !proches(courant.hc2, initial.hc2)) {
    corrections.heures_complementaires = { hc1: arrondi(courant.hc1), hc2: arrondi(courant.hc2) };
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
  if (courant.heuresRegulariseesAjoutees.length) {
    corrections.regularisations_heures_ajoutees = courant.heuresRegulariseesAjoutees;
  }
  if (courant.heuresRegulariseesRetirees.length) {
    corrections.regularisations_heures_retirees = courant.heuresRegulariseesRetirees;
  }
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
/** Ce qu'un enregistrement fait suivre, et ce qu'il ne fait pas (R-187). */
export const CE_QUI_SUIT_LA_CORRECTION =
  'À l’enregistrement, le bulletin est recalculé en entier : le net et les cumuls de ce mois suivent. La DSN et les exports du mois repartent de ce bulletin s’ils ne sont pas encore faits ; une DSN déjà déposée ou un export déjà sorti ne changent pas seuls, ils sont à refaire.';

/** Ce que la correction de cette ligne ne fait pas d'elle-même, à dire avant d'enregistrer. */
export function avisSurLaLigne(ligne: Pick<LigneCorrigeable, 'code' | 'bloc' | 'libelle' | 'mode'>): string | null {
  if (ligne.code?.startsWith('cotisation:reduction_generale')) {
    return 'La réduction générale se recalcule sur le cumul de l’année : l’écart corrigé ici revient le mois suivant. Pour une correction durable, corrigez les heures ou le brut.';
  }
  if (/^brut:(absence_conges_payes|indemnite_conges_payes|iccp)/.test(ligne.code ?? '')) {
    return 'Corriger cette ligne change le montant, pas le solde de congés : pour le solde, corrigez le congé posé ou ajustez le compteur sur la fiche du salarié.';
  }
  return null;
}

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

/**
 * La ligne telle que Martine l'avait calculée : une ligne corrigée porte la
 * valeur corrigée, et « Martine : 15 » donnait le taux corrigé pour celui de
 * Martine (jeu du 23/10). Refaire une correction retirée part aussi de là.
 */
export function valeursDeMartine(ligne: LigneCorrigeable): LigneCorrigeable {
  const calcule = ligne.valeur_calculee;
  if (!ligne.correction || !calcule) return ligne;
  const lu = (cle: string) => (cle in calcule ? calcule[cle] ?? null : undefined);
  const garder = (valeur: number | null | undefined, sinon: number | null | undefined) =>
    valeur === undefined ? sinon : valeur;
  if (ligne.bloc === 'brut') {
    return {
      ...ligne,
      base: garder(lu('quantite'), ligne.base),
      taux: garder(lu('taux'), ligne.taux),
      montant: garder(ligne.retenue ? lu('perte') : lu('gain'), ligne.montant),
    };
  }
  if (ligne.bloc === 'impot') {
    return { ...ligne, taux: garder(lu('taux'), ligne.taux), montant: garder(lu('montant'), ligne.montant) };
  }
  return {
    ...ligne,
    base: garder(lu('base'), ligne.base),
    taux_salarial: garder(lu('taux_salarial'), ligne.taux_salarial),
    taux_patronal: garder(lu('taux_patronal'), ligne.taux_patronal),
    montant_salarial: garder(lu('montant_salarial'), ligne.montant_salarial),
    montant_patronal: garder(lu('montant_patronal'), ligne.montant_patronal),
  };
}

/** Les champs que la ligne laisse corriger, avec la valeur de Martine. Rien pour une ligne qui ne se corrige pas ici. */
export function champsDeLaLigne(corrigeable: LigneCorrigeable): ChampDeLigne[] {
  const ligne = valeursDeMartine(corrigeable);
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
export function apercuDuMontant(corrigeable: LigneCorrigeable, cle: ChampCorrigeable, saisie: number): number | null {
  if (!Number.isFinite(saisie)) return null;
  const ligne = valeursDeMartine(corrigeable);
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
  // Une part corrigée se lit seule : la somme des deux parts faisait lire
  // « 35,24 € → 37,62 € » pour une part salariale de 17,62 € → 20 € (jeu du 23/10).
  // Une base corrigée change les deux parts : leur somme, dite comme telle.
  type Part = 'salarial' | 'patronal';
  const correction = ligne.correction ?? { base: null };
  const parBase = correction.base != null;
  const touchee = (part: Part) => correction[`montant_${part}`] != null || correction[`taux_${part}`] != null;
  const presente = (part: Part) =>
    Math.abs(calcule[`montant_${part}`] ?? 0) > 0 || Math.abs(ligne[`montant_${part}`] ?? 0) > 0;
  const touchees = (['salarial', 'patronal'] as const).filter((part) => (parBase ? presente(part) : touchee(part)));
  const parts: readonly Part[] = touchees.length ? touchees : ['salarial', 'patronal'];
  const avant = arrondi(parts.reduce((total, part) => total + (calcule[`montant_${part}`] ?? 0), 0));
  const apres = arrondi(parts.reduce((total, part) => total + (ligne[`montant_${part}`] ?? 0), 0));
  const precision = parts.length === 2 ? 'salarié + employeur' : parts[0] === 'salarial' ? 'part salariale' : 'part patronale';
  return `Martine : ${eurosFr(avant)} → corrigé : ${eurosFr(apres)} (${precision})`;
}

function nombreFr(valeur: number): string {
  return String(Math.round(valeur * 1e4) / 1e4).replace('.', ',');
}

const ORDRE_DES_CHAMPS: ChampCorrigeable[] = [
  'base',
  'taux',
  'montant',
  'taux_salarial',
  'taux_patronal',
  'montant_salarial',
  'montant_patronal',
];

/**
 * « Taux — Martine : 14,1347 → voulu : 15 · montant après correction : 2 275,05 € ».
 * La ligne « (à enregistrer) » ne montrait que son libellé et son motif.
 */
export function resumeDeLaCorrectionAEnregistrer(
  correction: CorrectionLigneAjoutee,
  ligne: LigneCorrigeable | undefined
): string {
  const cle = ORDRE_DES_CHAMPS.find((c) => correction[c] != null);
  if (!cle) return '';
  const tape = Number(correction[cle]);
  const voulu = TAUX_EN_POURCENT.has(cle) ? tape * 100 : tape;
  const champ = ligne ? champsDeLaLigne(ligne).find((c) => c.cle === cle) : undefined;
  const libelle = champ?.libelle ?? cle;
  const martine = champ?.valeur != null ? `Martine : ${nombreFr(champ.valeur)} → ` : '';
  const apercu = ligne ? apercuDuMontant(ligne, cle, voulu) : null;
  const montant = apercu !== null ? ` · montant après correction : ${eurosFr(apercu)}` : '';
  return `${libelle} — ${martine}voulu : ${nombreFr(voulu)}${montant}`;
}

/** Où se corrige une ligne qui ne se corrige pas ici, lisible sans survol. */
function ouSeCorrige(raison: string | null | undefined): string {
  const texte = raison ?? '';
  const lieu = texte.match(/«\s*([^»]+?)\s*»/)?.[1];
  if (lieu) return `se corrige dans « ${lieu} »`;
  if (/sous-total/i.test(texte)) return 'sous-total : corrigez ses lignes';
  if (/information/i.test(texte)) return 'ligne d’information, hors du brut';
  if (/régularisation de cotisation/i.test(texte)) return 'se corrige par une régularisation de cotisation';
  if (/source/i.test(texte)) return 'se corrige à sa source ou par une régularisation';
  return 'ne se corrige pas ici';
}

/**
 * Le libellé d'une ligne dans la liste « Ligne ». « Prime de jeu — se corrige
 * ailleurs » ne disait pas où : « Primes du mois » n'était que dans
 * l'infobulle, invisible au clavier et au tactile (jeu du 23/10).
 */
export function libelleDeLOption(ligne: LigneCorrigeable): string {
  return ligne.mode ? ligne.libelle : `${ligne.libelle} — ${ouSeCorrige(ligne.raison)}`;
}

/** Pourquoi « Ajouter la correction » est grisé, dit près du champ ; null quand tout est prêt. */
export function aideDeLaCorrection(
  valeur: string,
  motif: string
): { champ: 'valeur' | 'motif' | 'bouton'; message: string } | null {
  const tape = valeur.trim();
  const longueur = motif.trim().length;
  if (tape && lireNombre(tape) === null) {
    return { champ: 'valeur', message: 'La valeur voulue doit être un nombre, par exemple 15,5.' };
  }
  if (longueur > 0 && longueur < 3) {
    return { champ: 'motif', message: 'Le motif doit faire au moins 3 caractères.' };
  }
  if (!tape && longueur === 0) {
    return { champ: 'bouton', message: 'Tapez la valeur voulue et le motif pour ajouter la correction.' };
  }
  if (!tape) return { champ: 'bouton', message: 'Tapez la valeur voulue.' };
  if (longueur === 0) return { champ: 'bouton', message: 'Écrivez le motif : il est imprimé sur le bulletin.' };
  return null;
}

/** Le formulaire de la carte « Corriger une ligne », attaché à une version du bulletin. */
export interface FormulaireDeLigne {
  version: string | null;
  code: string;
  cle: ChampCorrigeable | '';
  valeur: string;
  motif: string;
  /** La correction en attente qu'on reporte sur une autre ligne. */
  reporterDe: string | null;
}

export function formulaireVide(version: string | null): FormulaireDeLigne {
  return { version, code: '', cle: '', valeur: '', motif: '', reporterDe: null };
}

/**
 * Après un enregistrement (nouvelle version du bulletin), la carte revient à
 * zéro : elle gardait la ligne choisie et disait en rouge « déjà corrigée »
 * juste après le succès (jeu du 23/10).
 */
export function formulaireDeLaVersion(formulaire: FormulaireDeLigne, version: string | null): FormulaireDeLigne {
  return formulaire.version === version ? formulaire : formulaireVide(version);
}

/**
 * Ce que l'onglet « Bulletin » demande à l'onglet « Corriger » (page client du 10/11, C1) :
 * ouvrir la bonne carte, pré-remplie. Le jeton change à chaque clic, même sur la même ligne.
 */
export type DemandeDeCorrection =
  | { carte: 'ligne'; code: string; jeton: number }
  | { carte: 'cotisation'; cotiId: string; libelle: string; jeton: number }
  | { carte: 'heures'; nature: NatureHeuresRegularisees; jeton: number };

function natureDeLaLigneDHeures(code: string): NatureHeuresRegularisees | null {
  const [, famille, pourcentage] = code.split('#')[0].split(':');
  const pct = lireNombre(pourcentage ?? '') ?? 0;
  if (famille === 'salaire_base') return 'normales';
  if (famille === 'heures_sup') return pct >= 50 ? 'hs2' : 'hs1';
  if (famille === 'heures_complementaires') return pct >= 25 ? 'hc2' : 'hc1';
  return null;
}

/**
 * Les deux gestes d'une ligne du bulletin : la corriger pour ce mois (carte
 * « Corriger une ligne »), ou régulariser un mois passé (carte des
 * régularisations de cotisation, ou d'heures pour le salaire et les heures).
 */
export function gestesDeLaLigne(
  ligne: Pick<LigneCorrigeable, 'code' | 'bloc' | 'libelle' | 'mode'>,
  jeton: number,
  options: { forfaitJours?: boolean } = {}
): { corriger: DemandeDeCorrection | null; regulariser: DemandeDeCorrection | null } {
  const code = ligne.code ?? '';
  const corriger: DemandeDeCorrection | null = code && ligne.mode ? { carte: 'ligne', code, jeton } : null;
  let regulariser: DemandeDeCorrection | null = null;
  if (ligne.bloc === 'cotisations' && code.startsWith('cotisation:') && !code.startsWith('cotisation:regularisation:')) {
    const cotiId = code.split('#')[0].split(':')[1];
    if (cotiId && cotiId !== 'sans_organisme') regulariser = { carte: 'cotisation', cotiId, libelle: ligne.libelle, jeton };
  } else if (ligne.bloc === 'brut' && !options.forfaitJours) {
    const nature = natureDeLaLigneDHeures(code);
    if (nature) regulariser = { carte: 'heures', nature, jeton };
  }
  return { corriger, regulariser };
}

/** Temps partiel au sens de C. trav. L3123-1 : une durée inférieure aux 35 h légales, ou cochée sur la fiche. */
export function estTempsPartiel(
  fiche: { is_temps_partiel?: boolean | null; duree_hebdomadaire?: number | null } | null | undefined
): boolean {
  if (!fiche) return false;
  if (fiche.is_temps_partiel) return true;
  const duree = fiche.duree_hebdomadaire;
  return typeof duree === 'number' && Number.isFinite(duree) && duree > 0 && duree < 35;
}
