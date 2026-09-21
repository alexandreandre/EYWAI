/**
 * Les jours à saisir, lus par la gestionnaire de paie : en semaines et en
 * plages (« S26 : 22/06–26/06 »), comme le serveur les nomme dans son 422.
 */

import { getISOWeek, getISOWeekYear, parseISO } from 'date-fns';

const jjmm = (iso: string): string => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

const lendemain = (iso: string): string => {
  const d = parseISO(iso);
  d.setDate(d.getDate() + 1);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const jj = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${jj}`;
};

/** Plages de jours consécutifs : `[[debut, fin], ...]`, dates ISO triées. */
export function plages(iso: string[]): [string, string][] {
  const out: [string, string][] = [];
  for (const jour of [...iso].sort()) {
    const derniere = out[out.length - 1];
    if (derniere && lendemain(derniere[1]) === jour) derniere[1] = jour;
    else out.push([jour, jour]);
  }
  return out;
}

/** « 22/06–26/06, 29/06–30/06 » — la même écriture que le message du serveur. */
export function libellePlages(iso: string[]): string {
  return plages(iso)
    .map(([a, b]) => (a === b ? jjmm(a) : `${jjmm(a)}–${jjmm(b)}`))
    .join(', ');
}

export interface SemaineASaisir {
  semaine: number;
  annee: number;
  libelle: string;
}

/** Une ligne par semaine ISO : « S26 : 22/06–26/06 ». */
export function regrouperParSemaine(iso: string[]): SemaineASaisir[] {
  const parSemaine = new Map<string, { semaine: number; annee: number; jours: string[] }>();
  for (const jour of [...iso].sort()) {
    const d = parseISO(jour);
    const semaine = getISOWeek(d);
    const annee = getISOWeekYear(d);
    const cle = `${annee}-${semaine}`;
    const entree = parSemaine.get(cle) ?? { semaine, annee, jours: [] };
    entree.jours.push(jour);
    parSemaine.set(cle, entree);
  }
  return [...parSemaine.values()].map(({ semaine, annee, jours }) => ({
    semaine,
    annee,
    libelle: `S${semaine} : ${libellePlages(jours)}`,
  }));
}
