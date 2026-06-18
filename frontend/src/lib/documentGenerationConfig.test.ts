import { describe, expect, it } from 'vitest';
import { parseEmployeeDocumentDeepLink } from './documentGenerationConfig';

describe('parseEmployeeDocumentDeepLink', () => {
  it('parse fiche_poste avec jobId', () => {
    expect(
      parseEmployeeDocumentDeepLink('tab=documents&generate=fiche_poste&jobId=job-123')
    ).toEqual({ generate: 'fiche_poste', jobId: 'job-123' });
  });

  it('retourne vide si pas de generate', () => {
    expect(parseEmployeeDocumentDeepLink('tab=documents')).toEqual({});
  });
});
