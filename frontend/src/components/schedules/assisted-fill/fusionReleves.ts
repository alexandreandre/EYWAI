import type {
  AffectedMonth,
  AiCalendarProposal,
  AiDayEntry,
  AiEmployeeProposal,
  CorrectionALaMain,
  LotPrecedent,
  ReimportInfo,
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

const deux = (n: number) => String(n).padStart(2, '0');
const AVERTISSEMENT_DU_JOUR = /^(\s*Jour )(\d{1,2}) : (.+)$/;

/**
 * « Jour 21 : … » d'un relevé devient « Jour 21/09/2026 : … » : fusionnés,
 * deux mois peuvent avoir un 21, l'avertissement dit lequel.
 */
function avertissementsDates(e: AiEmployeeProposal, releve: Mois): string[] {
  return e.warnings.map((w) => {
    const m = AVERTISSEMENT_DU_JOUR.exec(w);
    if (!m) return w;
    const numero = Number(m[2]);
    const leJour = e.days.find((d) => d.jour === numero);
    const mois = leJour ? moisDuJour(leJour, releve) : releve;
    return `${m[1]}${deux(numero)}/${deux(mois.month)}/${mois.year} : ${m[3]}`;
  });
}

const somme = (a?: number | null, b?: number | null) =>
  a == null && b == null ? null : (a ?? 0) + (b ?? 0);

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
    // Couverture : les jours attendus et lus de chaque fichier s'additionnent.
    const attendus = somme(prev.days_expected_count, emp.days_expected_count);
    const lus = somme(prev.days_imported_count, emp.days_imported_count);
    byKey.set(key, {
      ...prev,
      ...emp,
      days: [...dayMap.values()],
      warnings: [...new Set([...prev.warnings, ...emp.warnings])],
      days_expected_count: attendus,
      days_imported_count: lus,
      coverage_ratio: attendus && lus != null ? lus / attendus : emp.coverage_ratio,
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

interface Plage {
  start: string;
  end: string;
}

const lendemain = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${deux(d.getMonth() + 1)}-${deux(d.getDate())}`;
};

/** Les plages couvertes par les fichiers, fusionnées quand elles se touchent. */
function plagesCouvertes(proposals: AiCalendarProposal[]): Plage[] {
  const plages = proposals
    .flatMap((p): Plage[] =>
      p.detected_periods?.length
        ? p.detected_periods
        : p.detected_period_start && p.detected_period_end
          ? [{ start: p.detected_period_start, end: p.detected_period_end }]
          : [],
    )
    .sort((a, b) => a.start.localeCompare(b.start));
  const out: Plage[] = [];
  for (const p of plages) {
    const derniere = out[out.length - 1];
    if (derniere && p.start <= lendemain(derniere.end)) {
      if (p.end > derniere.end) derniere.end = p.end;
    } else {
      out.push({ ...p });
    }
  }
  return out;
}

/** Une relecture d'un des fichiers reste annoncée, quel que soit son rang. */
function relecturesFusionnees(proposals: AiCalendarProposal[]): ReimportInfo | null {
  const relectures = proposals.map((p) => p.reimport).filter((r): r is ReimportInfo => !!r);
  if (relectures.length === 0) return null;
  const lots = new Map<string, LotPrecedent>();
  const corrections = new Map<string, CorrectionALaMain>();
  const associations = new Set<string>();
  for (const r of relectures) {
    r.lots_precedents.forEach((l) => lots.set(l.batch_id, l));
    r.corrections_a_la_main.forEach((c) =>
      corrections.set(`${c.employee_id}|${c.annee}|${c.mois}|${c.jour}`, c),
    );
    (r.associations_reprises ?? []).forEach((a) => associations.add(a));
  }
  return {
    lots_precedents: [...lots.values()],
    corrections_a_la_main: [...corrections.values()],
    associations_reprises: [...associations],
  };
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

  // Une relecture dans la fusion : chaque jour dit s'il vient d'un fichier refait.
  const avecRelecture = proposals.some((p) => !!p.reimport);
  proposals.forEach((p) => {
    const releve: Mois = { year: p.year, month: p.month };
    const dates = p.employees.map((e) => ({
      ...e,
      warnings: avertissementsDates(e, releve),
      days: e.days.map((d) => ({
        ...dansLaFusion(d, releve, fusion),
        ...(avecRelecture ? { releve_refait: !!p.reimport } : {}),
      })),
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
  // Période affichée : l'union des fichiers (dates ISO, comparables en texte).
  const debuts = proposals.map((p) => p.detected_period_start).filter((x): x is string => !!x);
  const fins = proposals.map((p) => p.detected_period_end).filter((x): x is string => !!x);
  const datesLues = new Set(
    employees.flatMap((e) => e.days.map((d) => cleJour(d, fusion))),
  );
  return {
    ...base,
    detected_period_start: debuts.length ? debuts.sort()[0] : base.detected_period_start,
    detected_period_end: fins.length ? fins.sort()[fins.length - 1] : base.detected_period_end,
    detected_days_count: datesLues.size,
    detected_periods: plagesCouvertes(proposals),
    reimport: relecturesFusionnees(proposals) ?? base.reimport ?? null,
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
