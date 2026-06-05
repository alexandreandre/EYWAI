import { describe, expect, it } from 'vitest';
import {
  conventionDocumentFilename,
  getCachedConventionDocument,
  setCachedConventionDocument,
} from './collectiveAgreementDocumentCache';

describe('collectiveAgreementDocumentCache', () => {
  it('retourne null si absent du cache', () => {
    expect(getCachedConventionDocument('agr-1', 'full-text', 'hash-a')).toBeNull();
  });

  it('stocke et récupère un blob par convention, type et hash', () => {
    const blob = new Blob(['pdf'], { type: 'application/pdf' });
    setCachedConventionDocument('agr-1', 'synthesis', 'hash-a', blob, 'convention-1597-synthese.pdf');

    const hit = getCachedConventionDocument('agr-1', 'synthesis', 'hash-a');
    expect(hit?.filename).toBe('convention-1597-synthese.pdf');
    expect(hit?.blob).toBe(blob);

    expect(getCachedConventionDocument('agr-1', 'synthesis', 'hash-b')).toBeNull();
  });

  it('génère un nom de fichier cohérent', () => {
    expect(conventionDocumentFilename('1597', 'full-text')).toBe('convention-1597-texte-integral.pdf');
    expect(conventionDocumentFilename('1597', 'synthesis')).toBe('convention-1597-synthese.pdf');
  });
});
