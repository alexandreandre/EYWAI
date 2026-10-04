/**
 * Un bulletin dont les données d'entrée ont changé depuis le calcul.
 *
 * `a_recalculer` vaut true (périmé), false (empreinte identique) ou null
 * (bulletin d'avant l'empreinte, ou repris). Seul true porte le badge, le
 * bouton, et refuse la validation.
 */

import { estBulletinImporte } from './bulletinImporte';

export const MESSAGE_A_RECALCULER =
  'Le calendrier ou les absences ont changé depuis le calcul : recalculez avant de valider';

export const MESSAGE_COMPARAISON_INDISPONIBLE = 'recalculé, comparaison indisponible';

export type MontantsBulletin = {
  heures_sup: number | null;
  salaire_brut: number | null;
  net_a_payer: number | null;
};

export type LigneBulletinPaie = {
  year: number;
  month: number;
  origine?: string | null;
  a_recalculer?: boolean | null;
  heures_sup?: number | null;
  salaire_brut?: number | null;
  net_a_payer?: number | null;
};

export type SalariePourRelance = {
  id: string;
  first_name: string;
  last_name: string;
};

export type JobBulletinPerime = {
  employeeId: string;
  employeeName: string;
  year: number;
  month: number;
  montantsAvant: MontantsBulletin;
};

export function estPerime(
  payslip: { a_recalculer?: boolean | null; origine?: string | null } | null | undefined
): boolean {
  if (!payslip || estBulletinImporte(payslip)) return false;
  return payslip.a_recalculer === true;
}

/**
 * L'alerte « calendrier ou absences ont changé », sur le bulletin.
 *
 * Un bulletin est aussi périmé quand le mois d'avant a été recalculé depuis
 * son calcul : le serveur le dit alors par `a_regenerer`, qui s'affiche seul —
 * la phrase du calendrier serait fausse.
 */
export function alerteCalendrierChange(
  payslip:
    | { a_recalculer?: boolean | null; a_regenerer?: string | null; origine?: string | null }
    | null
    | undefined
): boolean {
  return estPerime(payslip) && !payslip?.a_regenerer;
}

function nombreOuNull(valeur: unknown): number | null {
  if (typeof valeur !== 'number' || !Number.isFinite(valeur)) return null;
  return valeur;
}

export function montantsDepuisLigne(
  ligne: {
    heures_sup?: number | null;
    salaire_brut?: number | null;
    net_a_payer?: number | null;
  } | null | undefined
): MontantsBulletin {
  return {
    heures_sup: nombreOuNull(ligne?.heures_sup),
    salaire_brut: nombreOuNull(ligne?.salaire_brut),
    net_a_payer: nombreOuNull(ligne?.net_a_payer),
  };
}

export function montantsDepuisReponse(
  reponse: {
    heures_sup?: number | null;
    salaire_brut?: number | null;
    net_a_payer?: number | null;
  } | null | undefined
): MontantsBulletin {
  return montantsDepuisLigne(reponse);
}

function comparaisonPossible(avant: MontantsBulletin, apres: MontantsBulletin): boolean {
  return (
    avant.heures_sup != null &&
    avant.salaire_brut != null &&
    avant.net_a_payer != null &&
    apres.heures_sup != null &&
    apres.salaire_brut != null &&
    apres.net_a_payer != null
  );
}

function fmtNombre(n: number): string {
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(n);
}

function fmtEuro(n: number): string {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(n);
}

export function libelleToastRecalcul(
  avant: MontantsBulletin | null | undefined,
  apres: MontantsBulletin | null | undefined
): { title: string; description: string } {
  if (!avant || !apres || !comparaisonPossible(avant, apres)) {
    return { title: 'Bulletin recalculé', description: MESSAGE_COMPARAISON_INDISPONIBLE };
  }
  return {
    title: 'Bulletin recalculé',
    description:
      `Heures sup. ${fmtNombre(avant.heures_sup!)} → ${fmtNombre(apres.heures_sup!)}` +
      ` · Brut ${fmtEuro(avant.salaire_brut!)} → ${fmtEuro(apres.salaire_brut!)}` +
      ` · Net ${fmtEuro(avant.net_a_payer!)} → ${fmtEuro(apres.net_a_payer!)}`,
  };
}

export function libelleBoutonRecalculerTout(n: number): string {
  return `Recalculer tout ce qui a changé (${n})`;
}

function nomDuSalarie(salarie: SalariePourRelance): string {
  return `${salarie.first_name} ${salarie.last_name}`.trim();
}

export function jobsDesLignesPerimes(
  salarie: SalariePourRelance,
  lignes: LigneBulletinPaie[]
): JobBulletinPerime[] {
  return lignes.filter(estPerime).map((ligne) => ({
    employeeId: salarie.id,
    employeeName: nomDuSalarie(salarie),
    year: ligne.year,
    month: ligne.month,
    montantsAvant: montantsDepuisLigne(ligne),
  }));
}

export function jobsDesBulletinsPerimes(
  salaries: SalariePourRelance[],
  bulletinsParSalarie: Record<string, LigneBulletinPaie[]>,
  year: number,
  month: number
): JobBulletinPerime[] {
  const jobs: JobBulletinPerime[] = [];
  for (const salarie of salaries) {
    const ligne = (bulletinsParSalarie[salarie.id] ?? []).find(
      (p) => p.year === year && p.month === month
    );
    if (!ligne || !estPerime(ligne)) continue;
    jobs.push({
      employeeId: salarie.id,
      employeeName: nomDuSalarie(salarie),
      year,
      month,
      montantsAvant: montantsDepuisLigne(ligne),
    });
  }
  return jobs;
}
