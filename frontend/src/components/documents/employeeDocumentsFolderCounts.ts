import type { GeneratedDocument } from '@/api/documents';
import {
  groupGeneratedByFolder,
  type DocumentFolderId,
  type PayslipItem,
} from '@/components/employee-detail/employeeDetailDocumentsFolders';

export interface ExitDocumentItem {
  id: string;
  name: string;
  url: string;
  previewUrl?: string;
  date?: string;
  isPublished?: boolean;
}

export function exitDocumentSubtitle(doc: ExitDocumentItem): string {
  if (!doc.date) {
    return doc.isPublished ? 'Document de sortie transmis' : 'Document de sortie';
  }
  const formatted = new Date(doc.date).toLocaleDateString('fr-FR');
  return doc.isPublished ? `Transmis le ${formatted}` : `Généré le ${formatted}`;
}

export interface ExpenseReceiptItem {
  id: string;
  name: string;
  url: string;
  subtitle: string;
}

export function filterVisibleGeneratedDocs(rows: GeneratedDocument[]): GeneratedDocument[] {
  return rows.filter((d) => d.status !== 'brouillon');
}

export function countEmployeeSelfFolderItems(
  folderId: DocumentFolderId,
  opts: {
    contractUrl: string | null;
    identityUrl: string | null;
    payslips: PayslipItem[];
    credentialsPdfUrl: string | null;
    generatedByFolder: ReturnType<typeof groupGeneratedByFolder>;
    exitDocuments: ExitDocumentItem[];
    expenseReceipts: ExpenseReceiptItem[];
  }
): number {
  switch (folderId) {
    case 'contrat':
      return (opts.contractUrl ? 1 : 0) + opts.generatedByFolder.contrat.length;
    case 'identite':
      return opts.identityUrl ? 1 : 0;
    case 'bulletins':
      return opts.payslips.length;
    case 'autres':
      return (
        opts.generatedByFolder.autres.length +
        opts.exitDocuments.length +
        opts.expenseReceipts.length +
        (opts.credentialsPdfUrl ? 1 : 0)
      );
    default:
      return 0;
  }
}

export function countRhDetailFolderItems(
  folderId: DocumentFolderId,
  opts: {
    contractUrl: string | null;
    identityUrl: string | null;
    payslips: PayslipItem[];
    credentialsPdfUrl: string | null;
    generatedByFolder: ReturnType<typeof groupGeneratedByFolder>;
  }
): number {
  switch (folderId) {
    case 'contrat':
      return (opts.contractUrl ? 1 : 0) + opts.generatedByFolder.contrat.length;
    case 'identite':
      return opts.identityUrl ? 1 : 0;
    case 'bulletins':
      return opts.payslips.length;
    case 'autres':
      return opts.generatedByFolder.autres.length + (opts.credentialsPdfUrl ? 1 : 0);
    default:
      return 0;
  }
}
