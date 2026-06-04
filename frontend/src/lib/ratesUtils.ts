import type { RateCategory, RatesResponse } from '@/api/rates';
import {
  getApiErrorStatus,
  getUserErrorMessage,
  sanitizeBackendMessage,
} from '@/lib/errorMessages';

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

export {
  formatEurAmount,
  formatFraisProArrayItemTitle,
  formatAvantagesEnNatureAmount,
  formatEffectifRange,
  formatHeuresSupPlage,
  formatIsoDateFr,
  formatPayrollPercent,
  formatPasZone,
  formatRateDisplayValue,
  formatRateKey,
  getCategoryTitle,
  getRateValueSuffix,
  getRateValueUnit,
  isRateKeyUnitless,
  isRepasForfaitRecord,
  buildSmicDisplaySections,
  buildIjPlafondsDisplaySections,
  resolvePssSections,
  resolveSmicSections,
  pickAvantagesEnNatureValue,
  AVANTAGES_EN_NATURE_FORFAIT_ROWS,
  REPAS_FORFAIT_SITUATION_KEYS,
} from '@/lib/ratesLabels';

/** Couleur indicative discrète : récent &lt; 14 j, intermédiaire &lt; 6 mois, ancien sinon. */
export function getRateDateColor(d?: string | null): string {
  if (!d) return 'text-red-600 dark:text-red-400';
  const diffDays =
    (Date.now() - new Date(d).getTime()) / (1000 * 60 * 60 * 24);
  if (diffDays < 14) return 'text-emerald-700 dark:text-emerald-500';
  if (diffDays < 180) return 'text-amber-700 dark:text-amber-500';
  return 'text-red-600 dark:text-red-400';
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
  const status = getApiErrorStatus(error);
  const detail = sanitizeBackendMessage(
    (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail,
  );
  if (status === 403) {
    return { message: 'Accès réservé aux RH et administrateurs.', status };
  }
  if (status === 404) {
    return {
      message:
        detail && (detail.includes('configuration') || detail.includes('source'))
          ? detail
          : 'Les taux ne sont pas encore disponibles. Lancez une mise à jour.',
      status,
    };
  }
  if (status === 409) {
    return { message: detail || 'Une mise à jour est déjà en cours.', status };
  }
  return {
    message: getUserErrorMessage(error, 'Une erreur est survenue.'),
    status,
  };
}

/** Cotisations gérées dans la fiche entreprise (ex. VM), pas via Suivi des taux. */
export const COMPANY_MANAGED_COTISATION_IDS = new Set(['versement_mobilite']);

export function isCompanyManagedCotisation(coti: Cotisation): boolean {
  const id = coti.id?.trim().toLowerCase() ?? '';
  if (COMPANY_MANAGED_COTISATION_IDS.has(id)) return true;
  const patronal = coti.patronal;
  return (
    typeof patronal === 'string' &&
    patronal.trim().toLowerCase() === 'specifique_entreprise'
  );
}

export function shouldShowCotisationInRates(coti: Cotisation): boolean {
  return !isCompanyManagedCotisation(coti);
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
  /** Horodatage du dernier contrôle scraping de cette ligne (si renseigné en base). */
  last_checked_at?: string | null;
};

export function resolveCotisationLastCheckedAt(
  coti: Cotisation,
): string | null | undefined {
  return coti.last_checked_at ?? null;
}

/** Date la plus récente parmi les cotisations d’un même groupe (base), sans repli section. */
export function latestCotisationLastCheckedAt(
  items: Cotisation[],
): string | null | undefined {
  let best: string | null | undefined = null;
  let bestMs = -1;
  for (const coti of items) {
    const at = resolveCotisationLastCheckedAt(coti);
    if (!at) continue;
    const ms = Date.parse(at);
    if (Number.isFinite(ms) && ms > bestMs) {
      bestMs = ms;
      best = at;
    }
  }
  return best ?? null;
}

