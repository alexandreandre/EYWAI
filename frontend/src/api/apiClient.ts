// src/api/apiClient.ts

import axios from 'axios';

/**
 * URL de l’API : injectée au build via VITE_API_URL (Docker / GitHub Actions).
 * En dev, `.env` pointe vers le backend local ; en prod, la variable dépôt GitHub du même nom.
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

  console.error(
    '[apiClient] VITE_API_URL est vide au build. Définis la variable dépôt GitHub VITE_API_URL (HTTPS du backend) pour les images Docker / la CI.',
  );
  return '';
}

const initialBaseUrl = getApiBaseUrl();

const apiClient = axios.create({
  baseURL: initialBaseUrl || undefined,
  headers: {
    'Content-Type': 'application/json',
  },
});

// NOTE: Le header X-Active-Company n'est PAS défini ici au démarrage.
// Il est géré dynamiquement par l'intercepteur de requêtes ci-dessous,
// qui le lit depuis localStorage à CHAQUE requête.
// Cela garantit qu'il est toujours à jour, même si l'utilisateur change d'entreprise.

apiClient.interceptors.request.use(
  (config) => {
    const baseUrl = getApiBaseUrl();
    if (baseUrl) {
      apiClient.defaults.baseURL = baseUrl;
      config.baseURL = baseUrl;
    }

    const token = localStorage.getItem('authToken');
    if (token && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    if (!config.headers['X-Active-Company']) {
      const activeCompanyId = localStorage.getItem('activeCompanyId');
      if (activeCompanyId) {
        config.headers['X-Active-Company'] = activeCompanyId;
      }
    }

    // multipart/form-data : le défaut application/json casse le boundary → 422 FastAPI
    if (config.data instanceof FormData) {
      const h = config.headers;
      if (h && typeof (h as { delete?: (key: string) => void }).delete === 'function') {
        (h as { delete: (key: string) => void }).delete('Content-Type');
      } else {
        delete (h as Record<string, unknown>)['Content-Type'];
      }
    }

    return config;
  },
  (error) => Promise.reject(error),
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('❌ ERREUR DE RÉPONSE:', {
      message: error.message,
      status: error.response?.status,
      data: error.response?.data,
    });
    return Promise.reject(error);
  },
);

export default apiClient;
