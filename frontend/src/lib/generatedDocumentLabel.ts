import type { GeneratedDocument } from '@/api/documents';
import { DOCUMENT_TYPE_LABELS } from '@/api/documentLibrary';

export function getGeneratedDocumentLabel(doc: GeneratedDocument): string {
  const custom = doc.generation_context?.custom_label;
  if (typeof custom === 'string' && custom.trim()) {
    return custom.trim();
  }
  return DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type;
}
