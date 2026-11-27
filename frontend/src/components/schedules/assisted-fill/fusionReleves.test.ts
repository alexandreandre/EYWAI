import { describe, expect, it } from 'vitest';
import type { AiCalendarProposal, AiDayEntry, AiEmployeeProposal } from '@/api/calendar';
import { mergeProposals } from './fusionReleves';

const jour = (j: number, heures: number, extra: Partial<AiDayEntry> = {}): AiDayEntry => ({
  jour: j,
  heures,
  type: 'travail',
  nature: 'reel',
  ...extra,
});

const salarie = (days: AiDayEntry[]): AiEmployeeProposal => ({
  raw_name: 'Salarié Un',
  employee_id: 'e1',
  matched_name: 'Salarié Un',
  match_confidence: 'high',
  time_tracking_id: null,
  review_status: 'ok',
  days,
  warnings: [],
});

const releve = (year: number, month: number, days: AiDayEntry[]): AiCalendarProposal => ({
  year,
  month,
  source: 'relevé tabulaire',
  employees: [salarie(days)],
  warnings: [],
});

const cle = (d: AiDayEntry, p: AiCalendarProposal) =>
  `${d.year ?? p.year}-${String(d.month ?? p.month).padStart(2, '0')}-${String(d.jour).padStart(2, '0')}`;

describe('mergeProposals : relevés de mois différents', () => {
  // Semaine 39 (lue en septembre) puis semaine 43 (octobre), importées ensemble.
  const septembre = releve(2026, 9, [jour(21, 7), jour(24, 7.25), jour(25, 6.75)]);
  const octobre = releve(2026, 10, [jour(21, 7), jour(22, 9.75), jour(23, 7)]);

  it('chaque jour garde sa vraie date : septembre ne s’écrit pas en octobre', () => {
    const fusion = mergeProposals([septembre, octobre]);
    const jours = fusion.employees[0].days.map((d) => [cle(d, fusion), d.heures]);
    expect(jours).toEqual([
      ['2026-09-21', 7],
      ['2026-09-24', 7.25],
      ['2026-09-25', 6.75],
      ['2026-10-21', 7],
      ['2026-10-22', 9.75],
      ['2026-10-23', 7],
    ]);
  });

  it('le même numéro de jour dans deux mois ne s’écrase pas', () => {
    const fusion = mergeProposals([septembre, octobre]);
    const le21 = fusion.employees[0].days.filter((d) => d.jour === 21);
    expect(le21.map((d) => cle(d, fusion))).toEqual(['2026-09-21', '2026-10-21']);
  });

  it('l’ordre des fichiers ne change rien aux dates', () => {
    const fusion = mergeProposals([octobre, septembre]);
    const dates = fusion.employees[0].days.map((d) => cle(d, fusion));
    expect(dates).toEqual([
      '2026-09-21', '2026-09-24', '2026-09-25', '2026-10-21', '2026-10-22', '2026-10-23',
    ]);
  });

  it('dit que la fusion touche plusieurs mois', () => {
    const fusion = mergeProposals([septembre, octobre]);
    expect(fusion.affected_months?.map((m) => `${m.month}/${m.year}`)).toEqual(['9/2026', '10/2026']);
  });

  it('un jour déjà daté (semaine à cheval) garde sa date', () => {
    const acheval = releve(2026, 10, [jour(30, 7, { year: 2026, month: 9 }), jour(1, 7)]);
    const fusion = mergeProposals([acheval, octobre]);
    expect(fusion.employees[0].days.map((d) => cle(d, fusion))).toEqual([
      '2026-09-30', '2026-10-01', '2026-10-21', '2026-10-22', '2026-10-23',
    ]);
  });

  it('dans un même mois, le dernier relevé l’emporte pour un même jour', () => {
    const avant = releve(2026, 10, [jour(21, 6)]);
    const fusion = mergeProposals([avant, octobre]);
    const le21 = fusion.employees[0].days.filter((d) => d.jour === 21);
    expect(le21).toHaveLength(1);
    expect(le21[0].heures).toBe(7);
  });
});

describe('mergeProposals : avertissements, période et couverture', () => {
  const avec = (p: AiCalendarProposal, extra: Partial<AiEmployeeProposal>, prop: Partial<AiCalendarProposal> = {}) => ({
    ...p,
    ...prop,
    employees: [{ ...p.employees[0], ...extra }],
  });

  const septembre = avec(
    releve(2026, 9, [jour(21, 7), jour(24, 7)]),
    {
      warnings: ['Jour 21 : Pointage incomplet.', 'Matricule absent.'],
      days_expected_count: 5,
      days_imported_count: 2,
      coverage_ratio: 0.4,
    },
    { detected_period_start: '2026-09-21', detected_period_end: '2026-09-25', detected_days_count: 2 },
  );
  const octobre = avec(
    releve(2026, 10, [jour(21, 7)]),
    {
      warnings: ['Jour 21 : Heures retenues vides.'],
      days_expected_count: 5,
      days_imported_count: 1,
      coverage_ratio: 0.2,
    },
    { detected_period_start: '2026-10-19', detected_period_end: '2026-10-23', detected_days_count: 1 },
  );

  it('les avertissements « Jour N » portent la date complète', () => {
    const fusion = mergeProposals([septembre, octobre]);
    expect(fusion.employees[0].warnings).toEqual([
      'Jour 21/09/2026 : Pointage incomplet.',
      'Matricule absent.',
      'Jour 21/10/2026 : Heures retenues vides.',
    ]);
  });

  it('la période affichée est l’union des fichiers', () => {
    const fusion = mergeProposals([octobre, septembre]);
    expect(fusion.detected_period_start).toBe('2026-09-21');
    expect(fusion.detected_period_end).toBe('2026-10-23');
    expect(fusion.detected_days_count).toBe(3);
  });

  it('la couverture du salarié additionne les fichiers', () => {
    const e = mergeProposals([septembre, octobre]).employees[0];
    expect(e.days_expected_count).toBe(10);
    expect(e.days_imported_count).toBe(3);
    expect(e.coverage_ratio).toBeCloseTo(0.3);
  });
});
