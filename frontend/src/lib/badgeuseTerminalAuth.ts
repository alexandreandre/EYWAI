import { BADGEUSE_RH_TERMINAL_PATH } from '@/lib/badgeuseRoutes';

const TERMINAL_TOKEN_KEY = 'badgeuseTerminalToken';
const TERMINAL_COMPANY_ID_KEY = 'badgeuseTerminalCompanyId';
const TERMINAL_LABEL_KEY = 'badgeuseTerminalLabel';
const TERMINAL_COMPANY_NAME_KEY = 'badgeuseTerminalCompanyName';
const TERMINAL_COMPANY_LOGO_KEY = 'badgeuseTerminalCompanyLogo';

export const BADGEUSE_TERMINAL_TOKEN_HEADER = 'X-Badgeuse-Terminal-Token';

export interface BadgeuseTerminalSession {
  token: string;
  companyId: string;
  label?: string;
  companyName?: string;
  companyLogoUrl?: string;
}

export function getTerminalToken(): string | null {
  return localStorage.getItem(TERMINAL_TOKEN_KEY);
}

export function getTerminalCompanyId(): string | null {
  return localStorage.getItem(TERMINAL_COMPANY_ID_KEY);
}

export function hasTerminalToken(): boolean {
  return Boolean(getTerminalToken());
}

export function persistTerminalSession(session: BadgeuseTerminalSession): void {
  localStorage.setItem(TERMINAL_TOKEN_KEY, session.token.trim());
  localStorage.setItem(TERMINAL_COMPANY_ID_KEY, session.companyId);
  if (session.label) {
    localStorage.setItem(TERMINAL_LABEL_KEY, session.label);
  }
  if (session.companyName) {
    localStorage.setItem(TERMINAL_COMPANY_NAME_KEY, session.companyName);
  }
  if (session.companyLogoUrl) {
    localStorage.setItem(TERMINAL_COMPANY_LOGO_KEY, session.companyLogoUrl);
  }
}

export function clearTerminalSession(): void {
  localStorage.removeItem(TERMINAL_TOKEN_KEY);
  localStorage.removeItem(TERMINAL_COMPANY_ID_KEY);
  localStorage.removeItem(TERMINAL_LABEL_KEY);
  localStorage.removeItem(TERMINAL_COMPANY_NAME_KEY);
  localStorage.removeItem(TERMINAL_COMPANY_LOGO_KEY);
}

export function readStoredTerminalSession(): BadgeuseTerminalSession | null {
  const token = getTerminalToken();
  const companyId = getTerminalCompanyId();
  if (!token || !companyId) return null;
  return {
    token,
    companyId,
    label: localStorage.getItem(TERMINAL_LABEL_KEY) ?? undefined,
    companyName: localStorage.getItem(TERMINAL_COMPANY_NAME_KEY) ?? undefined,
    companyLogoUrl: localStorage.getItem(TERMINAL_COMPANY_LOGO_KEY) ?? undefined,
  };
}

export function buildTerminalSetupUrl(token: string): string {
  const params = new URLSearchParams({ setup: token });
  return `${BADGEUSE_RH_TERMINAL_PATH}?${params.toString()}`;
}

export function buildDefaultTerminalLabel(): string {
  const ua = navigator.userAgent;
  let device = 'Navigateur';
  if (/iPad/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) {
    device = 'iPad';
  } else if (/iPhone/.test(ua)) {
    device = 'iPhone';
  } else if (/Android/.test(ua)) {
    device = 'Tablette Android';
  }
  const dateLabel = new Date().toLocaleDateString('fr-FR');
  return `${device} · ${dateLabel}`;
}

async function tryReuseExistingTerminal(companyId: string): Promise<boolean> {
  const session = readStoredTerminalSession();
  if (!session?.token) return false;
  if (session.companyId !== companyId && session.companyId !== 'pending') {
    clearTerminalSession();
    return false;
  }

  const { getTerminalStatus } = await import('@/api/badgeuseTerminal');
  try {
    const status = await getTerminalStatus();
    if (status.company_id !== companyId) {
      clearTerminalSession();
      return false;
    }
    persistTerminalSession({
      token: session.token,
      companyId: status.company_id,
      label: status.label,
      companyName: status.company_name ?? undefined,
    });
    return true;
  } catch {
    clearTerminalSession();
    return false;
  }
}

export interface OpenBadgeuseOnDeviceResult {
  opened: boolean;
  activated: boolean;
}

/** Active si besoin puis ouvre la badgeuse kiosque dans un nouvel onglet. */
export async function openBadgeuseOnThisDevice(
  companyId: string
): Promise<OpenBadgeuseOnDeviceResult> {
  const reused = await tryReuseExistingTerminal(companyId);
  let activated = false;

  if (!reused) {
    const { activateTerminalDeviceHere } = await import('@/api/badgeuseTerminal');
    const data = await activateTerminalDeviceHere(
      companyId,
      buildDefaultTerminalLabel()
    );
    persistTerminalSession({
      token: data.token,
      companyId,
      label: data.device.label,
    });
    activated = true;
  }

  const openedWindow = window.open(
    BADGEUSE_RH_TERMINAL_PATH,
    '_blank',
    'noopener,noreferrer'
  );
  if (!openedWindow) {
    throw new Error('Autorisez les fenêtres pop-up pour ouvrir la badgeuse.');
  }

  return { opened: true, activated };
}

export function consumeSetupTokenFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search);
  const setup = params.get('setup')?.trim();
  if (!setup) return null;
  const url = new URL(window.location.href);
  url.searchParams.delete('setup');
  window.history.replaceState({}, '', url.pathname + url.search);
  return setup;
}

export function isTerminalApiRequest(url: string | undefined): boolean {
  return Boolean(url?.includes('/api/badgeuse/terminal'));
}
