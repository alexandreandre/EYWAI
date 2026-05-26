import { log } from '@/lib/logger';

/**
 * URL de base de l'API (partagée par apiClient et authRefresh pour éviter les imports circulaires).
 */
export function getApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_URL as string | undefined;
  const trimmed = typeof raw === 'string' ? raw.trim() : '';

  if (trimmed) {
    let url = trimmed;
    if (!url.startsWith('http://') && !url.startsWith('https://') && !url.startsWith('/')) {
      url = `https://${url}`;
    }
    return url;
  }

  if (import.meta.env.DEV) {
    return 'http://localhost:8000';
  }

  log.error(
    '[apiClient] VITE_API_URL est vide au build. Définis la variable dépôt GitHub VITE_API_URL (HTTPS du backend) pour les images Docker / la CI.',
  );
  return '';
}
