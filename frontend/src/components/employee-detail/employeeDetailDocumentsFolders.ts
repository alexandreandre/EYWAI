import type { GeneratedDocument } from '@/api/documents';

export type DocumentFolderId = 'contrat' | 'identite' | 'bulletins' | 'autres';

export const DOCUMENT_FOLDERS: {
  id: DocumentFolderId;
  label: string;
  emptyMessage: string;
}[] = [
  {
    id: 'contrat',
    label: 'Contrat de travail',
    emptyMessage: 'Aucun contrat ni avenant pour ce collaborateur.',
  },
  {
    id: 'identite',
    label: "Pièce d'identité ou Titre de séjour",
    emptyMessage: 'Aucune pièce d’identité enregistrée.',
  },
  {
    id: 'bulletins',
    label: 'Bulletins de Paie',
    emptyMessage: 'Aucun bulletin de paie trouvé.',
  },
  {
    id: 'autres',
    label: 'Autres',
    emptyMessage: 'Aucun autre document pour le moment.',
  },
];

const AUTRES_CATEGORIES = new Set([
  'attestation_courante',
  'attestation_sortie',
  'attestation_situation',
]);

export function folderForGeneratedCategory(category: string): DocumentFolderId {
  if (category === 'contrat' || category === 'avenant') return 'contrat';
  if (AUTRES_CATEGORIES.has(category)) return 'autres';
  return 'autres';
}

export function groupGeneratedByFolder(rows: GeneratedDocument[]): Record<DocumentFolderId, GeneratedDocument[]> {
  const grouped: Record<DocumentFolderId, GeneratedDocument[]> = {
    contrat: [],
    identite: [],
    bulletins: [],
    autres: [],
  };
  for (const row of rows) {
    grouped[folderForGeneratedCategory(row.category)].push(row);
  }
  return grouped;
}

export interface PayslipItem {
  id: string;
  name: string;
  url: string;
  preview_url?: string;
  month: number;
  year: number;
}

export function sortPayslipsDesc(payslips: PayslipItem[]): PayslipItem[] {
  return [...payslips].sort((a, b) => b.year - a.year || b.month - a.month);
}

export function payslipLabel(p: PayslipItem): string {
  const raw = new Date(p.year, p.month - 1).toLocaleString('fr-FR', {
    month: 'long',
    year: 'numeric',
  });
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

export function groupPayslipsByYear(payslips: PayslipItem[]): Map<number, PayslipItem[]> {
  const map = new Map<number, PayslipItem[]>();
  for (const p of payslips) {
    const list = map.get(p.year) ?? [];
    list.push(p);
    map.set(p.year, list);
  }
  return new Map([...map.entries()].sort((a, b) => b[0] - a[0]));
}
