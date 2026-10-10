/**
 * Un bulletin dont les données d'entrée ont changé depuis le calcul.
 *
 * `a_recalculer` vaut true (périmé), false (empreinte identique) ou null
 * (bulletin d'avant l'empreinte, repris, ou d'un ancien contrat). Seul true
 * porte le badge, le bouton, et refuse la validation. `raison_a_recalculer`
 * dit ce qui a changé (« La mutuelle a changé… »).
 */

import { accord, pluriel } from '@/lib/pluriel';

import { estBulletinImporte } from './bulletinImporte';

/** Quand le serveur ne sait pas quelle donnée a changé (bulletin d'avant l'empreinte par partie). */
export const MESSAGE_A_RECALCULER =
  'Une donnée du bulletin a changé depuis le calcul (planning, absences, variables, fiche du salarié ou réglages de la société) : recalculez avant de valider.';

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
  /** « valide » une fois validé par la RH. */
  status?: string | null;
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
 * La phrase de l'alerte « À recalculer » du bulletin, ou null s'il n'y en a pas.
 *
 * Le serveur dit ce qui a changé dans ses entrées (`raison_a_recalculer`).
 * Un bulletin est aussi périmé quand le mois d'avant a été recalculé depuis
 * son calcul : `a_regenerer` le dit seul. Sans phrase du serveur, le message
 * général, qui ne prétend pas savoir quoi.
 */
export function messageARecalculer(
  payslip:
    | {
        a_recalculer?: boolean | null;
        a_regenerer?: string | null;
        raison_a_recalculer?: string | null;
        origine?: string | null;
        status?: string | null;
      }
    | null
    | undefined
): string | null {
  if (!payslip || estBulletinImporte(payslip)) return null;
  const message = payslip.raison_a_recalculer
    ? payslip.raison_a_recalculer
    : estPerime(payslip) && !payslip.a_regenerer
      ? MESSAGE_A_RECALCULER
      : null;
  return message && payslip.status === 'valide' ? pourBulletinValide(message) : message;
}

const FIN_RECALCULEZ = / depuis le calcul : recalculez avant de valider\.$/;

/** Un bulletin validé ne se « recalcule » pas avant validation : il se régénère, puis se valide de nouveau. */
function pourBulletinValide(message: string): string {
  const debut = FIN_RECALCULEZ.test(message)
    ? message.replace(FIN_RECALCULEZ, '')
    : 'Une donnée du bulletin a changé';
  return `${debut} depuis la validation : régénérez le bulletin (l’ancienne version est archivée), puis validez-le de nouveau.`;
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

import { deDevant } from './elision';

function fmtEuro(n: number): string {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(n);
}

export function libelleToastRecalcul(
  avant: MontantsBulletin | null | undefined,
  apres: MontantsBulletin | null | undefined,
  employeeName?: string
): { title: string; description: string } {
  const title = employeeName ? `Bulletin ${deDevant(employeeName)} recalculé` : 'Bulletin recalculé';
  if (!avant || !apres || !comparaisonPossible(avant, apres)) {
    return { title, description: MESSAGE_COMPARAISON_INDISPONIBLE };
  }
  return {
    title,
    description:
      `Heures sup. ${fmtNombre(avant.heures_sup!)} → ${fmtNombre(apres.heures_sup!)}` +
      ` · Brut ${fmtEuro(avant.salaire_brut!)} → ${fmtEuro(apres.salaire_brut!)}` +
      ` · Net ${fmtEuro(avant.net_a_payer!)} → ${fmtEuro(apres.net_a_payer!)}`,
  };
}

export type RecalculTermine = {
  employeeName: string;
  avant: MontantsBulletin | null | undefined;
  apres: MontantsBulletin | null | undefined;
};

const NOMBRE_MAX_DE_NOMS_DANS_LA_SYNTHESE = 10;

/**
 * Ce que l'écran dit à la fin des recalculs : un recalcul unitaire garde son
 * détail (avec le nom du salarié dans le titre) ; un lot tient en UN message,
 * avec les noms et le net avant → après.
 */
export function toastsDeFinDeRecalcul(
  recalculs: RecalculTermine[]
): { title: string; description: string }[] {
  if (recalculs.length === 0) return [];
  if (recalculs.length === 1) {
    const [r] = recalculs;
    return [libelleToastRecalcul(r.avant, r.apres, r.employeeName)];
  }
  const lignes = recalculs.slice(0, NOMBRE_MAX_DE_NOMS_DANS_LA_SYNTHESE).map((r) =>
    r.avant && r.apres && comparaisonPossible(r.avant, r.apres)
      ? `${r.employeeName} : net ${fmtEuro(r.avant.net_a_payer!)} → ${fmtEuro(r.apres.net_a_payer!)}`
      : `${r.employeeName} : ${MESSAGE_COMPARAISON_INDISPONIBLE}`
  );
  const reste = recalculs.length - lignes.length;
  if (reste > 0) lignes.push(`et ${pluriel(reste, 'autre')}`);
  return [
    {
      title: `${pluriel(recalculs.length, 'bulletin')} ${accord(recalculs.length, 'recalculé')}`,
      description: lignes.join(' · '),
    },
  ];
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
