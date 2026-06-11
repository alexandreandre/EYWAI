import { describe, expect, it } from 'vitest';
import {
  exitDocumentSubtitle,
  filterVisibleGeneratedDocs,
  countEmployeeSelfFolderItems,
} from '@/components/documents/employeeDocumentsFolderCounts';
import { groupGeneratedByFolder } from '@/components/employee-detail/employeeDetailDocumentsFolders';
import type { GeneratedDocument } from '@/api/documents';

function doc(status: string): GeneratedDocument {
  return {
    id: '1',
    company_id: 'c',
    employee_id: 'e',
    document_type: 'cdi',
    category: 'contrat',
    template_id: null,
    template_version_id: null,
    is_eywai_template: false,
    file_url: null,
    file_name: null,
    status,
    generation_context: {},
    generated_by: null,
    created_at: '2025-01-01',
    updated_at: '2025-01-01',
  };
}

describe('exitDocumentSubtitle', () => {
  it('distingue généré et transmis', () => {
    expect(
      exitDocumentSubtitle({
        id: '1',
        name: 'Certificat',
        url: 'http://x',
        date: '2026-06-01T10:00:00Z',
        isPublished: false,
      })
    ).toMatch(/^Généré le /);

    expect(
      exitDocumentSubtitle({
        id: '2',
        name: 'Certificat',
        url: 'http://x',
        date: '2026-06-10T10:00:00Z',
        isPublished: true,
      })
    ).toMatch(/^Transmis le /);
  });
});

describe('filterVisibleGeneratedDocs', () => {
  it('exclut les brouillons', () => {
    const rows = [doc('brouillon'), doc('envoye'), doc('signe')];
    expect(filterVisibleGeneratedDocs(rows).map((d) => d.status)).toEqual(['envoye', 'signe']);
  });
});

describe('countEmployeeSelfFolderItems', () => {
  it('compte contrat + générés', () => {
    const generatedByFolder = groupGeneratedByFolder([doc('envoye')]);
    expect(
      countEmployeeSelfFolderItems('contrat', {
        contractUrl: 'http://x',
        identityUrl: null,
        payslips: [],
        credentialsPdfUrl: null,
        generatedByFolder,
        exitDocuments: [],
        expenseReceipts: [],
      })
    ).toBe(2);
  });

  it('compte le PDF identifiants dans Autres', () => {
    const generatedByFolder = groupGeneratedByFolder([]);
    expect(
      countEmployeeSelfFolderItems('autres', {
        contractUrl: null,
        identityUrl: null,
        payslips: [],
        credentialsPdfUrl: 'http://credentials',
        generatedByFolder,
        exitDocuments: [],
        expenseReceipts: [],
      })
    ).toBe(1);
  });
});
