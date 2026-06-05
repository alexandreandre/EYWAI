/**
 * Logging frontend : calme par défaut (local + prod), verbeux seulement si VITE_APP_DEBUG=1.
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const TRUTHY = new Set(['1', 'true', 'yes', 'on']);

function envTruthy(name: string): boolean {
  const v = import.meta.env[name];
  if (typeof v !== 'string') return false;
  return TRUTHY.has(v.trim().toLowerCase());
}

/** Traces détaillées (login, company switcher, réponses API, etc.). */
export function isAppDebugEnabled(): boolean {
  return envTruthy('VITE_APP_DEBUG');
}

const levelEnabled: Record<LogLevel, boolean> = {
  debug: isAppDebugEnabled(),
  info: isAppDebugEnabled(),
  warn: true,
  error: true,
};

function emit(level: LogLevel, args: unknown[]): void {
  if (!levelEnabled[level]) return;
  const prefix = `[${level}]`;
  switch (level) {
    case 'debug':
      console.debug(prefix, ...args);
      break;
    case 'info':
      console.info(prefix, ...args);
      break;
    case 'warn':
      console.warn(prefix, ...args);
      break;
    case 'error':
      console.error(prefix, ...args);
      break;
  }
}

export const log = {
  debug: (...args: unknown[]) => emit('debug', args),
  info: (...args: unknown[]) => emit('info', args),
  warn: (...args: unknown[]) => emit('warn', args),
  error: (...args: unknown[]) => emit('error', args),
};

const WARNING_MARKERS =
  /ERREUR|ERROR|❌|\[WARNING\]|⚠|WARN:|échec|failed|exception/i;

function legacyConsoleLevel(args: unknown[]): LogLevel {
  const msg = args.map(String).join(' ');
  if (WARNING_MARKERS.test(msg)) return 'warn';
  return 'debug';
}

const DEV_CONSOLE_NOISE =
  /Download the React DevTools|React Router Future Flag Warning/;

/** Masque le bruit console connu des dépendances en dev (React, React Router). */
function suppressKnownDevConsoleNoise(): void {
  if (import.meta.env.PROD) return;

  (['log', 'info', 'warn', 'debug'] as const).forEach((method) => {
    const original = console[method].bind(console);
    console[method] = (...args: unknown[]) => {
      if (DEV_CONSOLE_NOISE.test(args.map(String).join(' '))) return;
      original(...args);
    };
  });
}

/** Shim pour les console.log non migrés dans src/. */
export function installConsoleShim(): void {
  suppressKnownDevConsoleNoise();

  if (isAppDebugEnabled()) return;

  const wrap =
    (original: (...a: unknown[]) => void) =>
    (...args: unknown[]) => {
      const level = legacyConsoleLevel(args);
      if (level === 'warn') {
        console.warn('[legacy]', ...args);
        return;
      }
      if (level === 'error') {
        console.error('[legacy]', ...args);
        return;
      }
      // debug/info silencieux
    };

  console.log = wrap(console.log.bind(console));
  console.debug = wrap(console.debug.bind(console));
  console.info = wrap(console.info.bind(console));
}
