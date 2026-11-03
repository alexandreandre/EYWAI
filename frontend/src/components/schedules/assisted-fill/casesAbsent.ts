/**
 * Case « absent » de la revue d'import (retour d'Elsa du 28/10/2026) : en
 * dépliant la ligne d'un salarié, chaque jour vide peut être coché « absent ».
 *
 * - Jour vide : lu sans heures (ou à 0 h) et de type travail, ou jour ouvré
 *   (lundi-vendredi) de la période du document que le relevé ne porte pas.
 * - Coché : le jour part au planning avec le type « absent, type à donner »
 *   (prévu) et un réel vide. Il ne retire aucun salaire ; la génération du
 *   bulletin est refusée, sans forçage, tant que la RH ne lui a pas donné son
 *   type au calendrier.
 * - Non coché : le jour reste vide, donc « à saisir », comme avant.
 */

import type { DayNature } from '@/api/calendar';
import { TYPE_ABSENT_A_TYPER } from '@/lib/absentATyper';

export interface JourRevu {
  jour: number;
  heures: number | null;
  type: string;
  nature: DayNature;
  year?: number | null;
  month?: number | null;
  /** Jour non lu ajouté par la case : décoché, il disparaît (rien n'est écrit). */
  ajoutParCase?: boolean;
}

export interface JourVide {
  jour: number;
  annee: number;
  mois: number;
  /** Présent dans le relevé (lu sans heures, ou déjà coché). */
  lu: boolean;
}

export interface PeriodeRevue {
  /** Période du document, ISO (yyyy-mm-dd) ; absente : seuls les jours lus comptent. */
  debut?: string | null;
  fin?: string | null;
  /** Mois affiché, pour les jours sans mois propre. */
  annee: number;
  mois: number;
}

const estVide = (j: JourRevu) =>
  j.type === TYPE_ABSENT_A_TYPER ||
  ((j.type === 'travail' || j.type === 'work') && (j.heures == null || j.heures === 0));

function cle(annee: number, mois: number, jour: number): string {
  return `${annee}-${mois}-${jour}`;
}

function datesOuvrees(debut: string, fin: string): { annee: number; mois: number; jour: number }[] {
  const out: { annee: number; mois: number; jour: number }[] = [];
  const d = new Date(`${debut}T12:00:00`);
  const f = new Date(`${fin}T12:00:00`);
  if (Number.isNaN(d.getTime()) || Number.isNaN(f.getTime())) return out;
  // Garde-fou : une période de plus de 62 jours n'est pas celle d'un relevé.
  for (let i = 0; d <= f && i < 62; i++) {
    const jds = d.getDay();
    if (jds !== 0 && jds !== 6) {
      out.push({ annee: d.getFullYear(), mois: d.getMonth() + 1, jour: d.getDate() });
    }
    d.setDate(d.getDate() + 1);
  }
  return out;
}

/** Les jours qu'on peut cocher « absent », dans l'ordre du calendrier. */
export function joursVides(jours: JourRevu[], periode: PeriodeRevue): JourVide[] {
  const parCle = new Map<string, JourRevu>();
  for (const j of jours) {
    parCle.set(cle(j.year ?? periode.annee, j.month ?? periode.mois, j.jour), j);
  }
  const out = new Map<string, JourVide>();
  for (const j of jours) {
    if (!estVide(j)) continue;
    const annee = j.year ?? periode.annee;
    const mois = j.month ?? periode.mois;
    out.set(cle(annee, mois, j.jour), { jour: j.jour, annee, mois, lu: true });
  }
  if (periode.debut && periode.fin) {
    for (const d of datesOuvrees(periode.debut, periode.fin)) {
      const k = cle(d.annee, d.mois, d.jour);
      if (!parCle.has(k)) out.set(k, { ...d, lu: false });
    }
  }
  return [...out.values()].sort(
    (a, b) => a.annee - b.annee || a.mois - b.mois || a.jour - b.jour
  );
}

const meme = (j: JourRevu, v: JourVide, periode: { annee: number; mois: number }) =>
  j.jour === v.jour && (j.year ?? periode.annee) === v.annee && (j.month ?? periode.mois) === v.mois;

/** Coche ou décoche « absent » sur un jour vide. */
export function basculerAbsent(jours: JourRevu[], vide: JourVide, coche: boolean): JourRevu[] {
  const periode = { annee: vide.annee, mois: vide.mois };
  const existant = jours.find((j) => meme(j, vide, periode));
  if (coche) {
    if (existant) {
      return jours.map((j) =>
        j === existant ? { ...j, type: TYPE_ABSENT_A_TYPER, heures: null } : j
      );
    }
    return [
      ...jours,
      {
        jour: vide.jour,
        heures: null,
        type: TYPE_ABSENT_A_TYPER,
        nature: 'reel',
        year: vide.annee,
        month: vide.mois,
        ajoutParCase: true,
      },
    ];
  }
  if (!existant) return jours;
  if (existant.ajoutParCase) return jours.filter((j) => j !== existant);
  return jours.map((j) => (j === existant ? { ...j, type: 'travail', heures: null } : j));
}

/**
 * Le jour coché part deux fois : au prévu (le type, que lisent les contrôles
 * de paie) et au réel (vide). Les autres jours partent tels quels.
 */
export function joursPourEnregistrement(jours: JourRevu[]): JourRevu[] {
  return jours.flatMap(({ ajoutParCase: _ajout, ...j }) =>
    j.type === TYPE_ABSENT_A_TYPER
      ? [
          { ...j, heures: null, nature: 'prevu' as DayNature },
          { ...j, heures: null, nature: 'reel' as DayNature },
        ]
      : [j]
  );
}

export function nombreAbsents(jours: JourRevu[]): number {
  return jours.filter((j) => j.type === TYPE_ABSENT_A_TYPER).length;
}

/** Ce que l'écran dit avant d'enregistrer, s'il y a des jours cochés. */
export function phraseAvantEnregistrement(n: number): string | null {
  if (n <= 0) return null;
  const types = '(congé, RTT, arrêt ou absence non payée)';
  return n === 1
    ? `1 jour marqué « absent » : la paie de ce salarié restera bloquée tant que vous ne lui aurez pas donné son type au calendrier ${types}.`
    : `${n} jours marqués « absent » : la paie restera bloquée tant que vous ne leur aurez pas donné leur type au calendrier ${types}.`;
}

export interface AbsentsDuSalarie {
  employeeId: string;
  nom: string;
  jours: number[];
}

/** Le récapitulatif après enregistrement : qui, quels jours. */
export function absentsMarques(
  lignes: { employeeId: string | null; nom: string; jours: JourRevu[] }[]
): AbsentsDuSalarie[] {
  return lignes
    .map((l) => ({
      employeeId: l.employeeId ?? '',
      nom: l.nom,
      jours: l.jours
        .filter((j) => j.type === TYPE_ABSENT_A_TYPER)
        .map((j) => j.jour)
        .sort((a, b) => a - b),
    }))
    .filter((l) => l.employeeId && l.jours.length > 0);
}
