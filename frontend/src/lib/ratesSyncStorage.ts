import type { RatesSyncTarget } from '@/lib/ratesSyncManifest';

const SESSIONS_KEY = 'eywai_rates_active_sync_sessions_v1';
const LEGACY_IDS_KEY = 'eywai_rates_active_sync_ids';

export type PersistedSyncSession = {
  syncId: string;
  target: RatesSyncTarget;
  isMonthly: boolean;
  createdAt?: string;
};

function isRatesSyncTarget(value: unknown): value is RatesSyncTarget {
  if (!value || typeof value !== 'object') return false;
  const scope = (value as { scope?: unknown }).scope;
  return (
    scope === 'all' ||
    scope === 'rate_key' ||
    scope === 'rate_keys' ||
    scope === 'source_key' ||
    scope === 'cotisation_id' ||
    scope === 'cotisation_bundle'
  );
}

function readRawSessions(): PersistedSyncSession[] {
  try {
    const raw = sessionStorage.getItem(SESSIONS_KEY);
    if (!raw) return migrateLegacyIds();
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return migrateLegacyIds();

    const sessions: PersistedSyncSession[] = [];
    for (const item of parsed) {
      if (!item || typeof item !== 'object') continue;
      const syncId = (item as { syncId?: unknown }).syncId;
      const target = (item as { target?: unknown }).target;
      if (typeof syncId !== 'string' || !syncId || !isRatesSyncTarget(target)) continue;
      sessions.push({
        syncId,
        target,
        isMonthly: Boolean((item as { isMonthly?: unknown }).isMonthly),
        createdAt:
          typeof (item as { createdAt?: unknown }).createdAt === 'string'
            ? (item as { createdAt: string }).createdAt
            : undefined,
      });
    }
    return sessions.length > 0 ? sessions : migrateLegacyIds();
  } catch {
    return migrateLegacyIds();
  }
}

function migrateLegacyIds(): PersistedSyncSession[] {
  try {
    const raw = sessionStorage.getItem(LEGACY_IDS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    const sessions = parsed
      .filter((id): id is string => typeof id === 'string' && id.length > 0)
      .map((syncId) => ({
        syncId,
        target: { scope: 'all' as const },
        isMonthly: false,
      }));
    if (sessions.length > 0) {
      writePersistedSyncSessions(sessions);
      sessionStorage.removeItem(LEGACY_IDS_KEY);
    }
    return sessions;
  } catch {
    return [];
  }
}

export function readPersistedSyncSessions(): PersistedSyncSession[] {
  return readRawSessions();
}

export function readPersistedSyncIds(): string[] {
  return readPersistedSyncSessions().map((s) => s.syncId);
}

export function writePersistedSyncSessions(sessions: PersistedSyncSession[]): void {
  const byId = new Map<string, PersistedSyncSession>();
  for (const session of sessions) {
    if (session.syncId) byId.set(session.syncId, session);
  }
  const unique = [...byId.values()];
  if (unique.length === 0) {
    sessionStorage.removeItem(SESSIONS_KEY);
    sessionStorage.removeItem(LEGACY_IDS_KEY);
    return;
  }
  sessionStorage.setItem(SESSIONS_KEY, JSON.stringify(unique));
}

export function writePersistedSyncIds(ids: string[]): void {
  const existing = readPersistedSyncSessions();
  const map = new Map(existing.map((s) => [s.syncId, s]));
  for (const id of ids) {
    if (!map.has(id)) {
      map.set(id, { syncId: id, target: { scope: 'all' }, isMonthly: false });
    }
  }
  const next = [...map.values()].filter((s) => ids.includes(s.syncId));
  writePersistedSyncSessions(next);
}

export function removePersistedSyncId(syncId: string): void {
  writePersistedSyncSessions(
    readPersistedSyncSessions().filter((session) => session.syncId !== syncId),
  );
}

export function findPersistedSyncSession(syncId: string): PersistedSyncSession | undefined {
  return readPersistedSyncSessions().find((session) => session.syncId === syncId);
}
