import type { GeneratedDocument } from '@/api/documents';
import type { ExplorerPayslipItem, ExplorerStorageItem } from '@/api/documents';
import {
  groupPayslipsByYear,
  type PayslipItem,
} from '@/components/employee-detail/employeeDetailDocumentsFolders';

export interface EmployeeGroupMeta {
  employeeId: string;
  employeeName: string;
}

const UNKNOWN_EMPLOYEE_ID = '__unknown__';
const UNKNOWN_EMPLOYEE_NAME = 'Collaborateur non renseigné';

export function employeeKey(id: string | null | undefined, name: string | null | undefined): EmployeeGroupMeta {
  if (id) {
    return {
      employeeId: id,
      employeeName: (name ?? '').trim() || 'Collaborateur',
    };
  }
  return { employeeId: UNKNOWN_EMPLOYEE_ID, employeeName: UNKNOWN_EMPLOYEE_NAME };
}

export function sortEmployeeGroups<T extends { meta: EmployeeGroupMeta }>(groups: T[]): T[] {
  return [...groups].sort((a, b) => {
    if (a.meta.employeeId === UNKNOWN_EMPLOYEE_ID) return 1;
    if (b.meta.employeeId === UNKNOWN_EMPLOYEE_ID) return -1;
    return a.meta.employeeName.localeCompare(b.meta.employeeName, 'fr', { sensitivity: 'base' });
  });
}

export function groupGeneratedByEmployee(
  rows: GeneratedDocument[]
): { meta: EmployeeGroupMeta; docs: GeneratedDocument[] }[] {
  const map = new Map<string, { meta: EmployeeGroupMeta; docs: GeneratedDocument[] }>();
  for (const doc of rows) {
    const meta = employeeKey(doc.employee_id, doc.employee_name);
    const key = meta.employeeId;
    const entry = map.get(key) ?? { meta, docs: [] };
    entry.docs.push(doc);
    map.set(key, entry);
  }
  return sortEmployeeGroups([...map.values()]);
}

export function groupStorageByEmployee(
  rows: ExplorerStorageItem[]
): { meta: EmployeeGroupMeta; items: ExplorerStorageItem[] }[] {
  const map = new Map<string, { meta: EmployeeGroupMeta; items: ExplorerStorageItem[] }>();
  for (const item of rows) {
    const meta = employeeKey(item.employee_id, item.employee_name);
    const key = meta.employeeId;
    const entry = map.get(key) ?? { meta, items: [] };
    entry.items.push(item);
    map.set(key, entry);
  }
  return sortEmployeeGroups([...map.values()]);
}

export function groupPayslipsByEmployee(
  payslips: PayslipItem[],
  metaById: Map<string, ExplorerPayslipItem>
): { meta: EmployeeGroupMeta; payslips: PayslipItem[] }[] {
  const map = new Map<string, { meta: EmployeeGroupMeta; payslips: PayslipItem[] }>();
  for (const p of payslips) {
    const row = metaById.get(p.id);
    const meta = employeeKey(row?.employee_id, row?.employee_name);
    const key = meta.employeeId;
    const entry = map.get(key) ?? { meta, payslips: [] };
    entry.payslips.push(p);
    map.set(key, entry);
  }
  for (const entry of map.values()) {
    entry.payslips.sort((a, b) => b.year - a.year || b.month - a.month);
  }
  return sortEmployeeGroups([...map.values()]);
}

/** Regroupe les bulletins d'un collaborateur par année si la liste est longue. */
export function payslipsContentBlocks(payslips: PayslipItem[]): PayslipItem[][] | Map<number, PayslipItem[]> {
  if (payslips.length > 12) {
    return groupPayslipsByYear(payslips);
  }
  return [payslips];
}

export function tokenizeSearchQuery(query: string): string[] {
  return query
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .split(/\s+/)
    .filter(Boolean);
}

/**
 * Recherche « sémantique » sur le nom affiché : tokens indépendants de l'ordre,
 * correspondance sur chaque partie du nom, initiales, sans tenir compte des accents.
 */
export function matchesEmployeeSemantic(employeeName: string, rawQuery: string): boolean {
  const tokens = tokenizeSearchQuery(rawQuery);
  if (tokens.length === 0) return true;

  const normalized = employeeName
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{M}/gu, '');
  if (!normalized) return false;

  const parts = normalized.split(/\s+/).filter(Boolean);
  const haystacks = new Set<string>([
    normalized,
    [...parts].reverse().join(' '),
    ...parts,
    parts.map((p) => p[0] ?? '').join(''),
  ]);

  return tokens.every((token) => {
    if ([...haystacks].some((h) => h.includes(token))) return true;
    if (token.length >= 2 && token.length <= parts.length) {
      const initials = parts.map((p) => p[0]).join('');
      if (initials.startsWith(token)) return true;
    }
    return parts.some((p) => p.startsWith(token));
  });
}

/** Recherche par tokens sur un ou plusieurs libellés (nom de fichier, type, etc.). */
export function matchesFileSemantic(labels: string[], rawQuery: string): boolean {
  const tokens = tokenizeSearchQuery(rawQuery);
  if (tokens.length === 0) return true;

  const hay = labels
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{M}/gu, '');

  if (!hay) return false;
  return tokens.every((token) => hay.includes(token));
}

export function countFilesInEmployeeGroups(
  groups: { docs?: GeneratedDocument[]; items?: ExplorerStorageItem[]; payslips?: PayslipItem[] }[]
): number {
  return groups.reduce((sum, g) => {
    return sum + (g.docs?.length ?? 0) + (g.items?.length ?? 0) + (g.payslips?.length ?? 0);
  }, 0);
}
