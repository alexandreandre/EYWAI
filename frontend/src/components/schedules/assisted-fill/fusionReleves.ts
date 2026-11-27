import type {
  AffectedMonth,
  AiCalendarProposal,
  AiDayEntry,
  AiEmployeeProposal,
} from '@/api/calendar';
import { accord, pluriel } from '@/lib/pluriel';

/**
 * Fusion de plusieurs relevés importés ensemble (une semaine par fichier).
 *
 * Chaque jour garde sa date complète : un relevé de septembre fusionné avec
 * un relevé d'octobre ne s'écrit plus sous son seul numéro dans le mois du
 * dernier fichier (27/11 : jours de la semaine 39 écrits du 21 au 25 octobre).
 * Un jour d'un autre mois que celui de la fusion porte son année et son mois ;
 * le serveur l'enregistre à sa vraie date.
 */

interface Mois {
  year: number;
  month: number;
}

const cleMois = (m: Mois) => m.year * 100 + m.month;

/** Date complète du jour : la sienne, sinon celle du relevé d'où il vient. */
function moisDuJour(d: AiDayEntry, releve: Mois): Mois {
  return { year: d.year ?? releve.year, month: d.month ?? releve.month };
}

/**
 * Jour relu dans le repère de la fusion : année et mois seulement s'ils
 * diffèrent du mois de la fusion (un jour du mois affiché reste « sans
 * mois », comme dans le lot du serveur).
 */
function dansLaFusion(d: AiDayEntry, releve: Mois, fusion: Mois): AiDayEntry {
  const m = moisDuJour(d, releve);
  return cleMois(m) === cleMois(fusion)
    ? { ...d, year: null, month: null }
    : { ...d, year: m.year, month: m.month };
}

const cleJour = (d: AiDayEntry, fusion: Mois) => cleMois(moisDuJour(d, fusion)) * 100 + d.jour;

export function mergeEmployeeProposals(
  existing: AiEmployeeProposal[],
  incoming: AiEmployeeProposal[],
  fusion: Mois,
): AiEmployeeProposal[] {
  const byKey = new Map<string, AiEmployeeProposal>();
  const keyOf = (e: AiEmployeeProposal) =>
    e.time_tracking_id ?? e.employee_id ?? e.raw_name;

  [...existing, ...incoming].forEach((emp) => {
    const key = keyOf(emp);
    const prev = byKey.get(key);
    if (!prev) {
      byKey.set(key, { ...emp, days: [...emp.days] });
      return;
    }
    const dayMap = new Map(prev.days.map((d) => [cleJour(d, fusion), d]));
    emp.days.forEach((d) => dayMap.set(cleJour(d, fusion), d));
    byKey.set(key, {
      ...prev,
      ...emp,
      days: [...dayMap.values()],
      warnings: [...new Set([...prev.warnings, ...emp.warnings])],
    });
  });
  return [...byKey.values()].map((e) => ({
    ...e,
    days: [...e.days].sort((a, b) => cleJour(a, fusion) - cleJour(b, fusion)),
  }));
}

function moisTouches(employees: AiEmployeeProposal[], fusion: Mois): AffectedMonth[] {
  const parMois = new Map<number, AffectedMonth>();
  employees.forEach((e) =>
    e.days.forEach((d) => {
      const m = moisDuJour(d, fusion);
      const entree = parMois.get(cleMois(m)) ?? { year: m.year, month: m.month, days: [] };
      if (!entree.days.includes(d.jour)) entree.days.push(d.jour);
      parMois.set(cleMois(m), entree);
    }),
  );
  return [...parMois.entries()]
    .sort(([a], [b]) => a - b)
    .map(([, m]) => ({ ...m, days: [...m.days].sort((a, b) => a - b) }));
}

export function mergeProposals(proposals: AiCalendarProposal[]): AiCalendarProposal {
  const base = proposals[proposals.length - 1];
  const fusion: Mois = { year: base.year, month: base.month };
  let employees: AiEmployeeProposal[] = [];
  const warnings = new Set<string>();
  let ready = 0;
  let warning = 0;
  let error = 0;
  let empty = 0;
  let incomplete = 0;
  let gap = 0;

  proposals.forEach((p) => {
    const releve: Mois = { year: p.year, month: p.month };
    const dates = p.employees.map((e) => ({
      ...e,
      days: e.days.map((d) => dansLaFusion(d, releve, fusion)),
    }));
    employees = mergeEmployeeProposals(employees, dates, fusion);
    p.warnings.forEach((w) => warnings.add(w));
  });

  employees.forEach((e) => {
    if (e.review_status === 'empty') empty += 1;
    else if (e.review_status === 'error' || !e.employee_id) error += 1;
    else if (e.quality_issue === 'extraction_incomplete') incomplete += 1;
    else if (e.quality_issue === 'weekly_total_gap') gap += 1;
    else if (e.review_status === 'warning' || e.match_confidence === 'medium') warning += 1;
    else ready += 1;
  });

  const mois = moisTouches(employees, fusion);
  return {
    ...base,
    employees,
    warnings: [...warnings],
    source: `${pluriel(proposals.length, 'relevé')} ${accord(proposals.length, 'fusionné')}`,
    affected_months: mois.length > 1 ? mois : base.affected_months,
    review_summary: {
      ready,
      warning,
      error,
      empty,
      incomplete,
      gap,
      total: employees.length,
    },
    quality_checks: proposals.flatMap((p) => p.quality_checks ?? []),
  };
}
