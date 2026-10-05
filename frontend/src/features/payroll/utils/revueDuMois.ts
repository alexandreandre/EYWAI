/**
 * Revue de la paie du mois, dans la liste : écart avec le mois précédent,
 * bulletins à revoir et ligne de synthèse.
 *
 * Tout se calcule avec les bulletins déjà chargés par la page Paie (brut, net,
 * heures sup de tous les mois) : aucun appel de plus. Avant, voir un écart
 * demandait d'ouvrir chaque bulletin (revue du 05/10).
 */

import { estBulletinImporte } from './bulletinImporte';
import { estPerime } from './bulletinARecalculer';
import { monthLabel } from './payrollMonth';

/** Au-delà, l'écart du net avec le mois précédent est mis en orange (comme R03 côté serveur). */
export const SEUIL_ECART_NET_PCT = 10;
/** Au-delà, les heures sup du mois sont mises en orange (comme R09 côté serveur). */
export const SEUIL_HEURES_SUP = 20;

export type BulletinPourRevue = {
  year: number;
  month: number;
  salaire_brut?: number | null;
  net_a_payer?: number | null;
  heures_sup?: number | null;
  status?: string | null;
  origine?: string | null;
  a_recalculer?: boolean | null;
  warnings?: string[] | null;
};

export type EcartMoisPrecedent = {
  /** Écart du net en %, null sans mois précédent comparable. */
  netPct: number | null;
  fort: boolean;
  /** Ce qui met la ligne en orange, en quelques mots ; null sinon. */
  raison: string | null;
};

/** Statuts d'une ligne de la paie du mois (ceux de `PayslipRowState`). */
export type StatutLigne = 'idle' | 'loading' | 'success' | 'error' | 'unavailable';

export type LigneDuMois = {
  statut: StatutLigne;
  bulletin?: BulletinPourRevue;
  /** Alertes affichées sur la ligne (celles du bulletin et de la dernière génération). */
  alertes?: string[];
  ecart?: EcartMoisPrecedent | null;
};

export type SyntheseDuMois = {
  attendus: number;
  generes: number;
  valides: number;
  totalBrut: number;
  totalNet: number;
  /** Net du mois précédent des mêmes salariés ; null s'ils n'en ont pas. */
  netPrecedent: number | null;
  ecartNetPct: number | null;
};

const TOLERANCE = 1e-9;

function nombre(valeur: number | null | undefined): number | null {
  return typeof valeur === 'number' && Number.isFinite(valeur) ? valeur : null;
}

export function moisPrecedent(year: number, month: number): { year: number; month: number } {
  return month <= 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };
}

function pourcentage(pct: number): string {
  const arrondi = Math.round(pct);
  if (arrondi === 0) return '0 %';
  return `${arrondi > 0 ? '+' : ''}${arrondi} %`;
}

function heures(n: number): string {
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(n);
}

function euros(n: number): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(n);
}

function libelleMoisPrecedent(year: number, month: number): string {
  const precedent = moisPrecedent(year, month);
  return monthLabel(precedent.month).toLowerCase();
}

function ecartPct(apres: number | null, avant: number | null): number | null {
  if (apres === null || avant === null || avant === 0) return null;
  return ((apres - avant) / Math.abs(avant)) * 100;
}

export function ecartAvecMoisPrecedent(
  courant: BulletinPourRevue,
  precedent: BulletinPourRevue | undefined
): EcartMoisPrecedent {
  const netPct = ecartPct(nombre(courant.net_a_payer), nombre(precedent?.net_a_payer));
  const heuresSup = nombre(courant.heures_sup) ?? 0;
  const netFort = netPct !== null && Math.abs(netPct) - SEUIL_ECART_NET_PCT > TOLERANCE;
  const heuresFortes = heuresSup - SEUIL_HEURES_SUP > TOLERANCE;
  const raisons: string[] = [];
  if (netFort && netPct !== null) {
    raisons.push(`Net ${pourcentage(netPct)} sur ${libelleMoisPrecedent(courant.year, courant.month)}`);
  }
  if (heuresFortes) raisons.push(`${heures(heuresSup)} h sup.`);
  return {
    netPct,
    fort: netFort || heuresFortes,
    raison: raisons.length > 0 ? raisons.join(' · ') : null,
  };
}

/** L'écart du net, en clair (« +3 % sur août »), pour la ligne ; null sans mois précédent. */
export function libelleEcart(ecart: EcartMoisPrecedent | null | undefined, year: number, month: number): string | null {
  if (!ecart || ecart.netPct === null) return null;
  return `${pourcentage(ecart.netPct)} sur ${libelleMoisPrecedent(year, month)}`;
}

export function aUneAlerte(ligne: LigneDuMois): boolean {
  const alertes = ligne.alertes ?? ligne.bulletin?.warnings ?? [];
  return alertes.length > 0 || (nombre(ligne.bulletin?.net_a_payer) ?? 0) < 0;
}

/** Sans bulletin, en échec, à recalculer, en alerte ou en écart fort. */
export function estARevoir(ligne: LigneDuMois): boolean {
  if (ligne.statut === 'idle' || ligne.statut === 'error') return true;
  if (ligne.statut !== 'success' || !ligne.bulletin) return false;
  return estPerime(ligne.bulletin) || aUneAlerte(ligne) || Boolean(ligne.ecart?.fort);
}

/** Validé, ou repris de l'ancien logiciel (il a été payé). */
export function estValideOuRepris(bulletin: BulletinPourRevue | undefined): boolean {
  if (!bulletin) return false;
  return bulletin.status === 'valide' || estBulletinImporte(bulletin);
}

export function syntheseDuMois(
  lignes: ReadonlyArray<{
    statut: StatutLigne;
    bulletin?: BulletinPourRevue;
    bulletinPrecedent?: BulletinPourRevue;
  }>
): SyntheseDuMois {
  let attendus = 0;
  let generes = 0;
  let valides = 0;
  let totalBrut = 0;
  let totalNet = 0;
  let netPrecedent: number | null = null;
  for (const ligne of lignes) {
    if (ligne.statut !== 'unavailable') attendus += 1;
    const bulletin = ligne.bulletin;
    if (!bulletin) continue;
    generes += 1;
    if (estValideOuRepris(bulletin)) valides += 1;
    totalBrut += nombre(bulletin.salaire_brut) ?? 0;
    totalNet += nombre(bulletin.net_a_payer) ?? 0;
    const avant = nombre(ligne.bulletinPrecedent?.net_a_payer);
    if (avant !== null) netPrecedent = (netPrecedent ?? 0) + avant;
  }
  return {
    attendus,
    generes,
    valides,
    totalBrut,
    totalNet,
    netPrecedent,
    ecartNetPct: generes > 0 ? ecartPct(totalNet, netPrecedent) : null,
  };
}

export function phraseSynthese(synthese: SyntheseDuMois, year: number, month: number): string {
  const morceaux = [
    `${synthese.generes}/${synthese.attendus} générés`,
    `${synthese.valides} validé${synthese.valides > 1 ? 's' : ''}`,
  ];
  if (synthese.generes > 0) {
    morceaux.push(`Brut ${euros(synthese.totalBrut)}`, `Net ${euros(synthese.totalNet)}`);
    if (synthese.ecartNetPct !== null) {
      morceaux.push(`${pourcentage(synthese.ecartNetPct)} sur ${libelleMoisPrecedent(year, month)}`);
    }
  }
  return morceaux.join(' · ');
}
