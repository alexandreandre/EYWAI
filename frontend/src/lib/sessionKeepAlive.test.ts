import { describe, expect, it } from 'vitest';
import {
  isBadgeuseTerminalPath,
  proactiveRefreshIntervalMs,
  resolveSessionKeepAliveMode,
  sessionCheckIntervalMs,
  shouldRunProactiveRefresh,
} from '@/lib/sessionKeepAlive';
import { BADGEUSE_RH_TERMINAL_PATH } from '@/lib/badgeuseRoutes';

describe('sessionKeepAlive', () => {
  it('détecte le terminal badgeuse', () => {
    expect(isBadgeuseTerminalPath(BADGEUSE_RH_TERMINAL_PATH)).toBe(true);
    expect(isBadgeuseTerminalPath('/badgeuse-rh/scan')).toBe(true);
    expect(isBadgeuseTerminalPath('/badgeuse-rh')).toBe(false);
  });

  it('active le mode kiosque sur le terminal', () => {
    expect(resolveSessionKeepAliveMode(BADGEUSE_RH_TERMINAL_PATH)).toBe('kiosk');
    expect(resolveSessionKeepAliveMode('/employees')).toBe('default');
  });

  it('renouvelle plus souvent en mode kiosque', () => {
    expect(proactiveRefreshIntervalMs('kiosk')).toBeLessThan(
      proactiveRefreshIntervalMs('default'),
    );
    expect(sessionCheckIntervalMs('kiosk')).toBeLessThan(
      sessionCheckIntervalMs('default'),
    );
  });

  it('bascule en mode kiosque sur la route terminal', () => {
    expect(resolveSessionKeepAliveMode('/employees')).toBe('default');
    expect(resolveSessionKeepAliveMode(BADGEUSE_RH_TERMINAL_PATH)).toBe('kiosk');
  });

  it('déclenche un refresh proactif après l’intervalle', () => {
    const interval = proactiveRefreshIntervalMs('default');
    const now = 1_000_000;
    expect(shouldRunProactiveRefresh(now - interval, now, interval)).toBe(true);
    expect(shouldRunProactiveRefresh(now - interval + 1, now, interval)).toBe(false);
    expect(shouldRunProactiveRefresh(null, now, interval)).toBe(true);
  });
});
