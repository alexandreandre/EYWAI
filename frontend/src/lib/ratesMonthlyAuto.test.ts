import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  clearMonthlyAutoSyncDone,
  getMonthlyAutoSyncState,
  isMonthlyAutoSyncEnabled,
  markMonthlyAutoSyncDone,
  RATES_AUTO_SYNC_MONTH_KEY,
  RATES_MONTHLY_AUTO_ENABLED_KEY,
  setMonthlyAutoSyncEnabled,
  shouldAutoStartMonthlySync,
} from '@/lib/ratesMonthlyAuto';

const storage: Record<string, string> = {};

describe('ratesMonthlyAuto', () => {
  beforeEach(() => {
    Object.keys(storage).forEach((k) => delete storage[k]);
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => storage[k] ?? null,
      setItem: (k: string, v: string) => {
        storage[k] = v;
      },
      removeItem: (k: string) => {
        delete storage[k];
      },
      clear: () => {
        Object.keys(storage).forEach((k) => delete storage[k]);
      },
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('does not auto-start outside the 1st', () => {
    vi.setSystemTime(new Date('2026-05-15T10:00:00'));
    expect(shouldAutoStartMonthlySync()).toBe(false);
  });

  it('auto-starts on the 1st when enabled and not done', () => {
    vi.setSystemTime(new Date('2026-05-01T10:00:00'));
    setMonthlyAutoSyncEnabled(true);
    expect(shouldAutoStartMonthlySync()).toBe(true);
  });

  it('does not auto-start on the 1st if already done this month', () => {
    vi.setSystemTime(new Date('2026-05-01T10:00:00'));
    markMonthlyAutoSyncDone();
    expect(shouldAutoStartMonthlySync()).toBe(false);
  });

  it('does not auto-start when paused', () => {
    vi.setSystemTime(new Date('2026-05-01T10:00:00'));
    setMonthlyAutoSyncEnabled(false);
    expect(shouldAutoStartMonthlySync()).toBe(false);
  });

  it('reset cycle allows auto-start again on the 1st', () => {
    vi.setSystemTime(new Date('2026-05-01T10:00:00'));
    markMonthlyAutoSyncDone();
    clearMonthlyAutoSyncDone();
    expect(shouldAutoStartMonthlySync()).toBe(true);
  });

  it('enabled by default', () => {
    expect(isMonthlyAutoSyncEnabled()).toBe(true);
    expect(localStorage.getItem(RATES_MONTHLY_AUTO_ENABLED_KEY)).toBeNull();
  });

  it('reports next run when not the 1st', () => {
    vi.setSystemTime(new Date('2026-05-12T10:00:00'));
    const state = getMonthlyAutoSyncState();
    expect(state.isFirstDayOfMonth).toBe(false);
    expect(state.statusLabel).toContain('juin');
    expect(localStorage.getItem(RATES_AUTO_SYNC_MONTH_KEY)).toBeNull();
  });
});
