const CHUNK_RELOAD_KEY = 'eywai-chunk-reload';

function isChunkLoadError(message: string): boolean {
  return (
    message.includes('Failed to fetch dynamically imported module') ||
    message.includes('Importing a module script failed') ||
    message.includes('error loading dynamically imported module')
  );
}

function reloadOnceAfterDeploy(): void {
  if (sessionStorage.getItem(CHUNK_RELOAD_KEY)) {
    sessionStorage.removeItem(CHUNK_RELOAD_KEY);
    return;
  }
  sessionStorage.setItem(CHUNK_RELOAD_KEY, '1');
  window.location.reload();
}

/** Recharge une fois si un chunk lazy 404 après déploiement (cache index.html / session ouverte). */
export function installChunkLoadRecovery(): void {
  window.addEventListener('vite:preloadError', (event) => {
    event.preventDefault();
    reloadOnceAfterDeploy();
  });

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    const message =
      reason instanceof Error ? reason.message : reason != null ? String(reason) : '';
    if (!isChunkLoadError(message)) return;
    event.preventDefault();
    reloadOnceAfterDeploy();
  });
}
