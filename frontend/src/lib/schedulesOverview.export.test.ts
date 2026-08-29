import { describe, expect, it } from 'vitest';
import {
  buildOverviewExportTable,
  type EmployeeCalendarOverviewRow,
} from './schedulesOverview';

function row(
  overrides: Partial<EmployeeCalendarOverviewRow> & {
    employee?: Partial<EmployeeCalendarOverviewRow['employee']>;
  } = {},
): EmployeeCalendarOverviewRow {
  return {
    employee: {
      id: 'e1',
      first_name: 'Ada',
      last_name: 'Lovelace',
      job_title: 'Développeuse',
      ...overrides.employee,
    },
    planned: [],
    actual: [],
    heuresPrevues: 151,
    heuresFaites: 150,
    ecart: -1,
    rowStatus: 'saisi',
    absenceConflictDays: [3],
    loadError: false,
    isForfaitJour: false,
    ...overrides,
  };
}

describe('buildOverviewExportTable', () => {
  it('construit les colonnes et le nom de fichier pour le mois', () => {
    const table = buildOverviewExportTable([row()], 2026, 8);
    expect(table.filenameBase).toBe('calendriers-2026-08');
    expect(table.headers).toContain('Nom');
    expect(table.records).toHaveLength(1);
    expect(table.records[0][0]).toBe('Lovelace');
    expect(table.records[0][1]).toBe('Ada');
    expect(table.records[0][3]).toBe('Saisi');
    expect(table.records[0][6]).toBe('-1.0 h');
    expect(table.records[0][7]).toBe('3');
  });

  it('utilise les jours pour un forfait jour', () => {
    const table = buildOverviewExportTable(
      [row({ isForfaitJour: true, heuresPrevues: 18, heuresFaites: 18, ecart: 0 })],
      2026,
      1,
    );
    expect(table.records[0][4]).toBe('18.0 j');
    expect(table.filenameBase).toBe('calendriers-2026-01');
  });
});
