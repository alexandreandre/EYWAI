export type ConventionDocumentKind = 'full-text' | 'synthesis';

type CacheEntry = {
  blob: Blob;
  filename: string;
};

const cache = new Map<string, CacheEntry>();

function cacheKey(
  agreementId: string,
  kind: ConventionDocumentKind,
  sourceTextHash?: string | null
): string {
  return `${agreementId}:${kind}:${sourceTextHash ?? 'unknown'}`;
}

export function getCachedConventionDocument(
  agreementId: string,
  kind: ConventionDocumentKind,
  sourceTextHash?: string | null
): CacheEntry | null {
  return cache.get(cacheKey(agreementId, kind, sourceTextHash)) ?? null;
}

export function setCachedConventionDocument(
  agreementId: string,
  kind: ConventionDocumentKind,
  sourceTextHash: string | null | undefined,
  blob: Blob,
  filename: string
): void {
  cache.set(cacheKey(agreementId, kind, sourceTextHash), { blob, filename });
}

export function conventionDocumentFilename(
  idcc: string,
  kind: ConventionDocumentKind
): string {
  const suffix = kind === 'full-text' ? 'texte-integral' : 'synthese';
  return `convention-${idcc}-${suffix}.pdf`;
}
