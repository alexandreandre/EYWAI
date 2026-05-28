import type { RateCategory, RatesResponse } from '@/api/rates';

export type RatesSnapshot = Record<string, { version: number; last_checked_at: string | null }>;

export function formatRateDate(d?: string | null): string {
  if (!d) return 'Inconnue';
  return new Date(d).toLocaleString('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

export function formatPercent(val: unknown): string {
  if (val === null || val === undefined) return '-';
  const num = Number(val);
  if (Number.isNaN(num)) return String(val);
  const v = num < 10 ? num * 100 : num;
  return `${v.toFixed(2).replace('.', ',')} %`;
}

export function formatRateKey(key: string): string {
  const normalized = key
    .replace(/_/g, ' ')
    .replace('taux moins 50', 'Taux < 50')
    .replace('taux 50 et plus', 'Taux 50+')
    .replace('patronal ', '')
    .replace('salarial ', '');

  const acronyms = new Set(['smic', 'pss', 'ijss', 'pas', 'csg', 'crds']);
  return normalized
    .split(' ')
    .filter(Boolean)
    .map((part) => {
      const lower = part.toLowerCase();
      if (acronyms.has(lower)) return lower.toUpperCase();
      return lower.charAt(0).toUpperCase() + lower.slice(1);
    })
    .join(' ');
}

/** Vert < 14j, orange < 6 mois, rouge sinon */
export function getRateDateColor(d?: string | null): string {
  if (!d) return 'text-red-500';
  const checkDate = new Date(d);
  const now = new Date();
  const diffDays = (now.getTime() - checkDate.getTime()) / (1000 * 60 * 60 * 24);
  if (diffDays < 14) return 'text-green-600';
  if (diffDays < 180) return 'text-orange-500';
  return 'text-red-500';
}

export function isRateStale(d?: string | null): boolean {
  if (!d) return true;
  const diffDays =
    (Date.now() - new Date(d).getTime()) / (1000 * 60 * 60 * 24);
  return diffDays >= 14;
}

export function isRateVeryStale(d?: string | null): boolean {
  if (!d) return true;
  const diffDays =
    (Date.now() - new Date(d).getTime()) / (1000 * 60 * 60 * 24);
  return diffDays >= 180;
}

export function buildRatesSnapshot(data: RatesResponse): RatesSnapshot {
  const snap: RatesSnapshot = {};
  for (const [key, cat] of Object.entries(data)) {
    snap[key] = {
      version: cat.version ?? 0,
      last_checked_at: cat.last_checked_at,
    };
  }
  return snap;
}

export function countChangedCategories(
  before: RatesSnapshot,
  after: RatesResponse,
): string[] {
  const changed: string[] = [];
  for (const [key, cat] of Object.entries(after)) {
    const prev = before[key];
    if (!prev) {
      changed.push(key);
      continue;
    }
    if (
      (cat.version ?? 0) !== prev.version ||
      cat.last_checked_at !== prev.last_checked_at
    ) {
      changed.push(key);
    }
  }
  return changed;
}

export function computeRatesSummary(data: RatesResponse) {
  const entries = Object.entries(data);
  let obsolete = 0;
  let oldest: string | null = null;
  let oldestDate: Date | null = null;

  for (const [, cat] of entries) {
    if (isRateStale(cat.last_checked_at)) obsolete += 1;
    if (cat.last_checked_at) {
      const d = new Date(cat.last_checked_at);
      if (!oldestDate || d < oldestDate) {
        oldestDate = d;
        oldest = cat.last_checked_at;
      }
    } else {
      obsolete += 1;
    }
  }

  const health =
    obsolete === 0 ? 'ok' : obsolete <= Math.ceil(entries.length / 3) ? 'warning' : 'critical';

  return {
    categoryCount: entries.length,
    obsoleteCount: obsolete,
    oldestCheck: oldest,
    health,
  } as const;
}

export {
  clearMonthlyAutoSyncDone,
  currentMonthKey,
  getMonthlyAutoSyncState,
  isMonthlyAutoSyncEnabled,
  markMonthlyAutoSyncDone,
  setMonthlyAutoSyncEnabled,
  shouldAutoStartMonthlySync,
} from '@/lib/ratesMonthlyAuto';

export function parseRatesError(error: unknown): { message: string; status?: number } {
  const err = error as {
    response?: { status?: number; data?: { detail?: string } };
    message?: string;
  };
  const status = err.response?.status;
  const detail = err.response?.data?.detail;
  if (status === 403) {
    return { message: 'Accès réservé aux RH et administrateurs.', status };
  }
  if (status === 404) {
    return {
      message:
        detail?.includes('configuration') || detail?.includes('source')
          ? detail
          : 'Référentiel vide — lancez une mise à jour depuis les sources officielles.',
      status,
    };
  }
  if (status === 409) {
    return { message: detail || 'Une mise à jour est déjà en cours.', status };
  }
  return {
    message: detail || err.message || 'Une erreur est survenue.',
    status,
  };
}

export type Cotisation = {
  id: string;
  libelle: string;
  base: string;
  salarial?: null | number | Record<string, number>;
  patronal?: null | number | Record<string, number>;
  patronal_plein?: number;
  patronal_reduit?: number;
  salarial_Alsace_Moselle?: number;
};

export function getCategoryTitle(key: string): string {
  const titles: Record<string, string> = {
    smic: 'SMIC',
    pss: 'Plafond Sécurité Sociale (PSS)',
    ij_plafonds: 'Plafonds IJSS',
    cotisations: 'Cotisations Sociales',
    pas: 'Prélèvement à la source (PAS)',
    frais_pro: 'Frais professionnels',
    avantages_en_nature: 'Avantages en nature',
  };
  return titles[key] ?? key.replaceAll('_', ' ');
}
