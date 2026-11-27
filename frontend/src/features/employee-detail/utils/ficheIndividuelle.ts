/**
 * Fiche individuelle d'un salarié (Excel, lot L18 du 27/11/2026) : la période
 * demandée, en mois AAAA-MM. Le serveur refuse les mêmes cas ; l'écran le dit
 * avant d'envoyer.
 */
export interface PeriodeFiche {
  debut: string;
  fin: string;
}

export const MOIS_MAXIMUM_FICHE = 36;

export function periodeParDefaut(aujourdHui: Date = new Date()): PeriodeFiche {
  const annee = aujourdHui.getFullYear();
  return { debut: `${annee}-01`, fin: `${annee}-12` };
}

const MOIS = /^(\d{4})-(0[1-9]|1[0-2])$/;

function rang(mois: string): number | null {
  const m = MOIS.exec(mois);
  return m ? Number(m[1]) * 12 + Number(m[2]) - 1 : null;
}

/** Pourquoi la période est refusée, ou null si elle convient. */
export function messagePeriode({ debut, fin }: PeriodeFiche): string | null {
  const premier = rang(debut);
  const dernier = rang(fin);
  if (premier === null) return 'Choisissez le premier mois de la période.';
  if (dernier === null) return 'Choisissez le dernier mois de la période.';
  if (premier > dernier) return 'Le premier mois est après le dernier.';
  if (dernier - premier + 1 > MOIS_MAXIMUM_FICHE) {
    return `Période trop longue : ${MOIS_MAXIMUM_FICHE} mois au plus.`;
  }
  return null;
}
