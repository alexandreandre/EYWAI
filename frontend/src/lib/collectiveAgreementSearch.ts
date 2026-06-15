import type { CollectiveAgreementCatalog } from '@/api/collectiveAgreements';

export type CollectiveAgreementSearchFields = Pick<
  CollectiveAgreementCatalog,
  'name' | 'idcc' | 'sector' | 'description'
>;

function normalizeSearchText(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

export function searchTokens(query: string): string[] {
  const normalized = normalizeSearchText(query);
  if (!normalized) return [];
  const tokens = normalized.split(' ').filter((token) => token.length >= 2 || /^\d+$/.test(token));
  return tokens.length > 0 ? tokens : [normalized];
}

export function buildAgreementSearchBlob(agreement: CollectiveAgreementSearchFields): string {
  return normalizeSearchText(
    [agreement.name, agreement.idcc, agreement.sector, agreement.description]
      .filter(Boolean)
      .join(' ')
  );
}

export function matchesCollectiveAgreementSearch(
  agreement: CollectiveAgreementSearchFields,
  query: string
): boolean {
  const cleaned = query.trim();
  if (!cleaned) return true;
  const blob = buildAgreementSearchBlob(agreement);
  return searchTokens(cleaned).every((token) => blob.includes(token));
}

export function rankCollectiveAgreementSearch(
  agreement: CollectiveAgreementSearchFields,
  query: string
): number {
  const cleaned = query.trim();
  if (!cleaned) return 0;

  const blob = buildAgreementSearchBlob(agreement);
  const tokens = searchTokens(cleaned);
  let score = 0;

  const idcc = normalizeSearchText(agreement.idcc ?? '');
  const queryNorm = normalizeSearchText(cleaned);
  if (idcc && (queryNorm === idcc || queryNorm === idcc.replace(/^0+/, ''))) {
    score += 200;
  } else if (idcc && /^\d+$/.test(queryNorm) && idcc.startsWith(queryNorm)) {
    score += 150;
  }

  const name = normalizeSearchText(agreement.name ?? '');
  const sector = normalizeSearchText(agreement.sector ?? '');

  for (const token of tokens) {
    if (name.startsWith(token)) score += 80;
    else if (name.includes(token)) score += 50;
    if (sector.includes(token)) score += 40;
    if (blob.includes(token)) score += 10;
  }

  return score;
}

export function filterCollectiveAgreements<T extends CollectiveAgreementSearchFields>(
  agreements: T[],
  query: string,
  limit?: number
): T[] {
  const cleaned = query.trim();
  if (!cleaned) {
    return limit != null ? agreements.slice(0, limit) : agreements;
  }

  const filtered = agreements.filter((item) => matchesCollectiveAgreementSearch(item, cleaned));
  filtered.sort((a, b) => {
    const scoreDiff = rankCollectiveAgreementSearch(b, cleaned) - rankCollectiveAgreementSearch(a, cleaned);
    if (scoreDiff !== 0) return scoreDiff;
    return (a.name ?? '').localeCompare(b.name ?? '', 'fr');
  });

  return limit != null ? filtered.slice(0, limit) : filtered;
}

export function collectiveAgreementCommandValue(agreement: CollectiveAgreementSearchFields): string {
  return [agreement.name, agreement.idcc, agreement.sector, agreement.description]
    .filter(Boolean)
    .join(' ');
}
