import { describe, expect, it } from 'vitest';

import {
  duplicateWeekLabels,
  filesMissingWeek,
  weeksAlignedWithFiles,
} from './importWeekAssignments';

const files = [{ name: 'a.pdf' }, { name: 'b.pdf' }, { name: 'c.pdf' }];
const options = [
  { value: '2026-07-06', week: 28 },
  { value: '2026-07-13', week: 29 },
];

describe('importWeekAssignments', () => {
  it('aligne les semaines sur les fichiers, null quand non précisée', () => {
    expect(weeksAlignedWithFiles(files, { 'a.pdf': '2026-07-06', 'c.pdf': '2026-07-13' })).toEqual([
      '2026-07-06',
      null,
      '2026-07-13',
    ]);
  });

  it('liste les fichiers sans semaine', () => {
    expect(filesMissingWeek(files, { 'a.pdf': '2026-07-06' })).toEqual(['b.pdf', 'c.pdf']);
  });

  it('signale une semaine donnée à deux fichiers', () => {
    expect(
      duplicateWeekLabels(files, { 'a.pdf': '2026-07-06', 'b.pdf': '2026-07-06' }, options),
    ).toEqual(['S28']);
    expect(duplicateWeekLabels(files, { 'a.pdf': '2026-07-06' }, options)).toEqual([]);
  });
});

describe('weeksOutsideWindow', () => {
  it('rend, une fois chacune, les semaines choisies qui sortent de la fenêtre du mois', async () => {
    const { weeksOutsideWindow } = await import('./importWeekAssignments');
    const options = [
      { value: '2026-07-20', week: 30, horsFenetre: false },
      { value: '2026-07-27', week: 31, horsFenetre: true, paieDe: { year: 2026, month: 8 } },
    ];
    const files = [{ name: 'a.pdf' }, { name: 'b.pdf' }, { name: 'c.pdf' }];

    const hors = weeksOutsideWindow(
      files,
      { 'a.pdf': '2026-07-20', 'b.pdf': '2026-07-27', 'c.pdf': '2026-07-27' },
      options,
    );

    expect(hors.map((o) => o.week)).toEqual([31]);
  });
});
