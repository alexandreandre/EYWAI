// src/api/apiClient.ts

import axios from 'axios';

// URL de prod en HTTPS (évite Mixed Content) — utilisée dès que la page est en HTTPS
const PRODUCTION_API_URL = 'https://sirh-backend-505040845625.europe-west1.run.app';

function getApiBaseUrl(): string {
  // 🔍 DEBUG: Logs détaillés pour diagnostiquer Mixed Content
  const debugInfo: any = {
    timestamp: new Date().toISOString(),
    windowExists: typeof window !== 'undefined',
    windowLocation: typeof window !== 'undefined' ? window.location?.href : 'N/A',
    windowProtocol: typeof window !== 'undefined' ? window.location?.protocol : 'N/A',
    viteApiUrl: import.meta.env.VITE_API_URL,
    viteApiUrlType: typeof import.meta.env.VITE_API_URL,
    productionApiUrl: PRODUCTION_API_URL,
  };

  // En production (page en HTTPS), toujours utiliser l'URL HTTPS pour éviter Mixed Content
  if (typeof window !== 'undefined' && window.location?.protocol === 'https:') {
    debugInfo.decision = 'FORCE_HTTPS_PRODUCTION';
    debugInfo.finalUrl = PRODUCTION_API_URL;
    console.group('%c🔍 [DEBUG getApiBaseUrl] FORCE HTTPS (page en HTTPS)', 'background: #00ff00; color: black; font-weight: bold;');
    console.table(debugInfo);
    console.groupEnd();
    return PRODUCTION_API_URL;
  }

  const defaultUrl = PRODUCTION_API_URL;
  let url = import.meta.env.VITE_API_URL || defaultUrl;
  debugInfo.initialUrl = url;

  if (!url || url === '/') {
    url = defaultUrl;
    debugInfo.afterEmptyCheck = url;
  }

  if (!url.startsWith('http://') && !url.startsWith('https://') && !url.startsWith('/')) {
    url = `https://${url}`;
    debugInfo.afterSchemeAdd = url;
  }

  debugInfo.decision = 'USE_ENV_OR_DEFAULT';
  debugInfo.finalUrl = url;
  debugInfo.isHttp = url.startsWith('http://');
  debugInfo.isHttps = url.startsWith('https://');

  console.group('%c🔍 [DEBUG getApiBaseUrl] Calcul URL', 'background: #ffff00; color: black; font-weight: bold;');
  console.table(debugInfo);
  console.groupEnd();

  return url;
}

// 🔍 DEBUG: Log de l'URL initiale au chargement du module
const initialBaseUrl = getApiBaseUrl();
console.group('%c🔍 [DEBUG apiClient] INITIALISATION', 'background: #ff00ff; color: white; font-weight: bold;');
console.log('Initial baseURL:', initialBaseUrl);
console.log('Type:', typeof initialBaseUrl);
console.log('Starts with http://:', initialBaseUrl.startsWith('http://'));
console.log('Starts with https://:', initialBaseUrl.startsWith('https://'));
console.groupEnd();

const apiClient = axios.create({
  baseURL: initialBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
});

// NOTE: Le header X-Active-Company n'est PAS défini ici au démarrage.
// Il est géré dynamiquement par l'intercepteur de requêtes ci-dessous,
// qui le lit depuis localStorage à CHAQUE requête.
// Cela garantit qu'il est toujours à jour, même si l'utilisateur change d'entreprise.

// Intercepteur pour LOGGUER chaque requête avant son envoi
apiClient.interceptors.request.use(
  (config) => {
    // 🔍 DEBUG: Log détaillé AVANT recalcul
    const baseUrlBefore = config.baseURL || apiClient.defaults.baseURL;
    const fullUrlBefore = baseUrlBefore ? `${baseUrlBefore}${config.url || ''}` : config.url;

    // 0. Sécurité : recalculer la base URL à chaque requête pour garantir HTTPS en prod (évite Mixed Content)
    const baseUrl = getApiBaseUrl();
    apiClient.defaults.baseURL = baseUrl;
    config.baseURL = baseUrl;

    // 🔍 DEBUG: Log détaillé APRÈS recalcul
    const fullUrlAfter = `${config.baseURL}${config.url || ''}`;
    console.group(`%c🔍 [DEBUG INTERCEPTOR] ${config.method?.toUpperCase()} ${config.url}`, 'background: #ff6600; color: white; font-weight: bold;');
    console.log('📍 baseURL AVANT recalcul:', baseUrlBefore);
    console.log('📍 baseURL APRÈS recalcul:', baseUrl);
    console.log('📍 apiClient.defaults.baseURL:', apiClient.defaults.baseURL);
    console.log('📍 config.baseURL:', config.baseURL);
    console.log('🌐 URL COMPLÈTE AVANT:', fullUrlBefore);
    console.log('🌐 URL COMPLÈTE APRÈS:', fullUrlAfter);
    console.log('⚠️  URL contient http://:', fullUrlAfter.includes('http://'));
    console.log('✅ URL contient https://:', fullUrlAfter.includes('https://'));
    console.log('🔒 window.location.protocol:', typeof window !== 'undefined' ? window.location?.protocol : 'N/A');
    console.log('🔒 window.location.href:', typeof window !== 'undefined' ? window.location?.href : 'N/A');
    console.groupEnd();
    
    // 1. Ajouter le token d'authentification
    const token = localStorage.getItem('authToken');
    if (token && !config.headers.Authorization) {
        config.headers.Authorization = `Bearer ${token}`;
    }

    // 2. Ajouter le header X-Active-Company (système multi-entreprises)
    // Le header est lu depuis localStorage à CHAQUE requête pour garantir qu'il est toujours à jour
    const currentHeaderValue = config.headers['X-Active-Company'];
    console.log('%c[apiClient] 📋 Header X-Active-Company AVANT lecture localStorage:', 'background: yellow; color: black;', currentHeaderValue || 'NON DÉFINI');

    if (!currentHeaderValue) {
      const activeCompanyId = localStorage.getItem('activeCompanyId');
      console.log('%c[apiClient] 📂 Lecture localStorage activeCompanyId:', 'background: blue; color: white;', activeCompanyId || 'NULL');

      if (activeCompanyId) {
        config.headers['X-Active-Company'] = activeCompanyId;
        console.log('%c[apiClient] ✅ Header X-Active-Company DÉFINI depuis localStorage:', 'background: green; color: white;', activeCompanyId);
      } else {
        console.log('%c[apiClient] ⚠️ PAS de activeCompanyId dans localStorage - header NON défini', 'background: orange; color: white;');
      }
    } else {
      console.log('%c[apiClient] ℹ️  Header X-Active-Company déjà présent (priorité max):', 'background: purple; color: white;', currentHeaderValue);
    }

    // --- NOUVEAU LOG PLUS PRÉCIS ---
    const finalFullUrl = `${config.baseURL}${config.url}`;
    console.groupCollapsed(`%c🚀 REQUÊTE SORTANTE: ${config.method?.toUpperCase()} ${config.url}`, 'color: #0077cc; font-weight: bold;');
    console.log('%c🌐 URL COMPLÈTE FINALE:', finalFullUrl.startsWith('https://') ? 'color: #00ff00; font-weight: bold;' : 'color: #ff0000; font-weight: bold;', finalFullUrl);
    console.log('%c📍 baseURL:', 'color: #0077cc;', config.baseURL);
    console.log('%c📍 url relative:', 'color: #0077cc;', config.url);
    console.log('%c⚠️  PROTOCOLE:', finalFullUrl.startsWith('http://') ? 'color: #ff0000; font-weight: bold;' : 'color: #00ff00;', finalFullUrl.startsWith('http://') ? 'HTTP (⚠️ MIXED CONTENT!)' : 'HTTPS ✅');
    console.log('%cHEADER Authorization:', 'color: #0077cc;', config.headers.Authorization || '--- NON DÉFINI ---');
    console.log('%cHEADER X-Active-Company:', 'color: #ff6600;', config.headers['X-Active-Company'] || '--- NON DÉFINI ---');
    console.log('%cTOUS LES HEADERS:', 'color: #0077cc;', config.headers);
    console.log('%cDATA:', 'color: #0077cc;', config.data);
    console.groupEnd();
    // --- FIN DU NOUVEAU LOG ---

    return config;
  },
  (error) => {
    console.error('❌ ERREUR AVANT ENVOI:', error);
    return Promise.reject(error);
  }
);

// Intercepteur pour LOGGUER chaque réponse à sa réception
apiClient.interceptors.response.use(
  (response) => {
    console.log('%c✅ RÉPONSE REÇUE:', 'color: #009966;', {
      status: response.status,
      data: response.data,
    });
    return response;
  },
  (error) => {
    console.error('❌ ERREUR DE RÉPONSE:', {
      message: error.message,
      status: error.response?.status,
      data: error.response?.data,
    });
    return Promise.reject(error);
  }
);


export default apiClient;
