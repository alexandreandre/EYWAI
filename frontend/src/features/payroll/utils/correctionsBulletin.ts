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
import type { PayslipEditRequest, PrimeAjoutee } from '@/api/payslips';
import type { MonthlyInputCreate } from '@/api/saisies';
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
}

export interface EtatCorrections {
  hs25: number;
  hs50: number;
  revenirAuPlanning: boolean;
  primes: PrimeDuBulletin[];
  primesRetirees: string[];
  primesAjoutees: PrimeAjoutee[];
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

export function etatInitial(data: unknown, pdfNotes: string | null | undefined): EtatCorrections {
  const [hs25, hs50] = quantitesHeuresSup(data);
  return {
    hs25,
    hs50,
    revenirAuPlanning: false,
    primes: primesDuBulletin(data),
    primesRetirees: [],
    primesAjoutees: [],
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
