import { addDays, format } from 'date-fns';
import { fr } from 'date-fns/locale';

import { getISOWeekInfo } from '@/lib/analyticsPeriod';

export interface ImportWeekOption {
  /** Lundi de la semaine (YYYY-MM-DD) — c'est ce que le backend attend en `week_anchor_date`. */
  value: string;
  isoYear: number;
  week: number;
  /** « S27 · 29 juin – 5 juil. » */
  label: string;
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
