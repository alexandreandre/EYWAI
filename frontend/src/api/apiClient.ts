// src/api/apiClient.ts

import { log } from '@/lib/logger';
import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import {
  retryAxiosRequest,
  shouldRetryRequest,
  type RetryAxiosRequestConfig,
} from './apiRetry';
import { refreshAccessToken } from './authRefresh';
import { getApiBaseUrl } from './apiConfig';
import {
  clearAuthSession,
  getAccessToken,
  shouldRefreshAccessToken,
} from '@/lib/authSession';
import { isAppDebugEnabled, log } from '@/lib/logger';

export { getApiBaseUrl } from './apiConfig';

const initialBaseUrl = getApiBaseUrl();

type AuthAxiosConfig = InternalAxiosRequestConfig & {
  _authRetry?: boolean;
  _authRefreshAttempted?: boolean;
};

const apiClient = axios.create({
  baseURL: initialBaseUrl || undefined,
  headers: {
    'Content-Type': 'application/json',
  },
});

function isAuthRoute(url: string | undefined): boolean {
  if (!url) return false;
  return (
    url.includes('/api/auth/login') ||
    url.includes('/api/auth/refresh') ||
    url.includes('/api/auth/me')
  );
}

function redirectToLoginExpired(): void {
  clearAuthSession();
  delete apiClient.defaults.headers.common['Authorization'];
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login?session=expired';
  }
}

// NOTE: Le header X-Active-Company n'est PAS défini ici au démarrage.
// Il est géré dynamiquement par l'intercepteur de requêtes ci-dessous,
// qui le lit depuis localStorage à CHAQUE requête.
// Cela garantit qu'il est toujours à jour, même si l'utilisateur change d'entreprise.

apiClient.interceptors.request.use(
  async (config) => {
    const baseUrl = getApiBaseUrl();
    if (baseUrl) {
      apiClient.defaults.baseURL = baseUrl;
      config.baseURL = baseUrl;
    }

    const authConfig = config as AuthAxiosConfig;
    const requestUrl = authConfig.url ?? '';

    if (
      !isAuthRoute(requestUrl) &&
      shouldRefreshAccessToken() &&
      !authConfig._authRefreshAttempted
    ) {
      authConfig._authRefreshAttempted = true;
      const newToken = await refreshAccessToken();
      if (newToken) {
        apiClient.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
      }
    }

    const token = getAccessToken();
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
  async (error: AxiosError) => {
    const config = error.config as RetryAxiosRequestConfig | undefined;

    if (config && shouldRetryRequest(error)) {
      try {
        return await retryAxiosRequest((cfg) => apiClient.request(cfg), config);
      } catch (retryError) {
        error = retryError as AxiosError;
      }
    }

    const status = error.response?.status;
    const authConfig = config as AuthAxiosConfig | undefined;
    const requestUrl = authConfig?.url ?? '';

    if (
      status === 401 &&
      authConfig &&
      !authConfig._authRetry &&
      !isAuthRoute(requestUrl)
    ) {
      authConfig._authRetry = true;
      const newToken = await refreshAccessToken();
      if (newToken) {
        authConfig.headers = authConfig.headers ?? {};
        authConfig.headers.Authorization = `Bearer ${newToken}`;
        apiClient.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
        return apiClient.request(authConfig);
      }
      redirectToLoginExpired();
    }

    const payload = {
      message: error.message,
      status,
      url: requestUrl,
    };
    if (status && status >= 500) {
      log.error('[apiClient] Erreur HTTP:', payload);
    } else if (isAppDebugEnabled()) {
      log.debug('[apiClient] Erreur HTTP:', payload);
    }
    return Promise.reject(error);
  },
);

export default apiClient;
