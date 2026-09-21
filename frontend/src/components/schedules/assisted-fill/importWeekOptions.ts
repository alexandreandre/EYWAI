import { addDays, format } from 'date-fns';
import { fr } from 'date-fns/locale';

import { getISOWeekInfo } from '@/lib/analyticsPeriod';

export interface ImportWeekOption {
  /** Lundi de la semaine (YYYY-MM-DD) — c'est ce que le backend attend en `week_anchor_date`. */
  value: string;
  isoYear: number;
  week: number;
  /** « S27 · 29 juin – 5 juil. », suffixé « → paie d'août » hors de la fenêtre du mois. */
  label: string;
  /** Mois de paie auquel la semaine appartient (fenêtre des variables), si connu. */
  paieDe?: { year: number; month: number };
  /** Vrai quand la semaine appartient à la paie d'un autre mois que celui affiché. */
  horsFenetre?: boolean;
}

/** Ce qu'il faut de la fenêtre des variables (`GET /payroll-variables/period`). */
export interface FenetreDuMois {
  debut: string;
  fin: string;
  mois_civil: [string, string];
}

/**
 * Semaines ISO (lundi–dimanche) qui chevauchent le mois affiché, de la
 * semaine du 1er à celle du dernier jour. En paie on parle en « S27 »,
 * pas en « semaine commençant le 29/06 » : le numéro est l'entrée, le
 * lundi reste la valeur transmise.
 */
export function monthIsoWeekOptions(year: number, month: number): ImportWeekOption[] {
  const firstDay = new Date(year, month - 1, 1);
  const lastDay = new Date(year, month, 0);
  let monday = addDays(firstDay, -((firstDay.getDay() + 6) % 7));
  const options: ImportWeekOption[] = [];

  while (monday <= lastDay) {
    const { isoYear, week } = getISOWeekInfo(monday);
    const sunday = addDays(monday, 6);
    options.push({
      value: format(monday, 'yyyy-MM-dd'),
      isoYear,
      week,
      label: `S${week} · ${format(monday, 'd MMM', { locale: fr })} – ${format(sunday, 'd MMM', { locale: fr })}`,
    });
    monday = addDays(monday, 7);
  }

  return options;
}


/** « d'août », « de juin » : le mois de paie, avec l'élision. */
export function libellePaieDe(month: number): string {
  const nom = format(new Date(2026, month - 1, 1), 'MMMM', { locale: fr });
  return /^[aeiouyàâéèêëîïôöûü]/i.test(nom) ? `d'${nom}` : `de ${nom}`;
}

const moisSuivant = (year: number, month: number) =>
  month === 12 ? { year: year + 1, month: 1 } : { year, month: month + 1 };
const moisPrecedent = (year: number, month: number) =>
  month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };

/**
 * Les semaines à proposer pour le mois affiché, avec leur mois de paie.
 *
 * Les variables (heures sup, paniers) suivent une fenêtre de semaines
 * complètes, pas le mois civil : chez Colorplast, juillet 2026 court du 22/06
 * au 26/07 (S26–S30) et S31 appartient à août — les dossiers de Gaëlle sont
 * rangés ainsi. On propose donc les semaines de la fenêtre et du mois civil,
 * et l'on nomme la paie de celles qui sortent de la fenêtre. Sans fenêtre, ou
 * en mois civil, rien ne change.
 */
export function payrollWeekOptions(
  year: number,
  month: number,
  fenetre: FenetreDuMois | null | undefined,
): ImportWeekOption[] {
  if (!fenetre) return monthIsoWeekOptions(year, month);
  const [debutMois, finMois] = fenetre.mois_civil;
  if (fenetre.debut === debutMois && fenetre.fin === finMois) {
    return monthIsoWeekOptions(year, month);
  }

  const premier = new Date(`${fenetre.debut < debutMois ? fenetre.debut : debutMois}T00:00:00`);
  const dernier = new Date(`${fenetre.fin > finMois ? fenetre.fin : finMois}T00:00:00`);
  let monday = addDays(premier, -((premier.getDay() + 6) % 7));
  const options: ImportWeekOption[] = [];

  while (monday <= dernier) {
    const { isoYear, week } = getISOWeekInfo(monday);
    const sunday = addDays(monday, 6);
    const value = format(monday, 'yyyy-MM-dd');
    const paieDe =
      value < fenetre.debut
        ? moisPrecedent(year, month)
        : value > fenetre.fin
          ? moisSuivant(year, month)
          : { year, month };
    const horsFenetre = paieDe.month !== month || paieDe.year !== year;
    const bornes = `S${week} · ${format(monday, 'd MMM', { locale: fr })} – ${format(sunday, 'd MMM', { locale: fr })}`;
    options.push({
      value,
      isoYear,
      week,
      label: horsFenetre ? `${bornes} → paie ${libellePaieDe(paieDe.month)}` : bornes,
      paieDe,
      horsFenetre,
    });
    monday = addDays(monday, 7);
  }

  return options;
}
