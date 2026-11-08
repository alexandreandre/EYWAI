import { describe, expect, it } from 'vitest';
import type { GeneratedDocument } from '@/api/documents';
import { getGeneratedDocumentLabel } from '@/lib/generatedDocumentLabel';

function doc(partial: Partial<GeneratedDocument>): GeneratedDocument {
  return {
    id: '1',
    company_id: 'c1',
    employee_id: 'e1',
    document_type: 'document_transmis',
    category: 'attestation_courante',
    template_id: null,
    template_version_id: null,
    is_eywai_template: false,
    file_url: 'path',
    file_name: 'file.pdf',
    status: 'envoye',
    generation_context: {},
    generated_by: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...partial,
  };
}

describe('getGeneratedDocumentLabel', () => {
  it('utilise custom_label si présent', () => {
    expect(
      getGeneratedDocumentLabel(
        doc({ generation_context: { custom_label: '  Attestation mutuelle  ' } }),
      ),
    ).toBe('Attestation mutuelle');
  });

  it('retombe sur le libellé du type', () => {
    expect(
      getGeneratedDocumentLabel(
        doc({ document_type: 'attestation_emploi', generation_context: {} }),
      ),
    ).toBe("Attestation d'emploi");
  });
});
