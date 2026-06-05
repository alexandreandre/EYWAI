import axios from 'axios';

import { toast } from '@/hooks/use-toast';

/**
 * Système d'erreur centralisé (frontend).
 *
 * Objectif : ne JAMAIS exposer de jargon technique (messages serveur bruts,
 * traces, noms de variables d'environnement, messages Axios en anglais…) à un
 * utilisateur RH ou salarié. Tout passe par `getUserErrorMessage`, qui :
 *   1. mappe les erreurs réseau / serveur sur des phrases claires en français ;
 *   2. réutilise le message métier renvoyé par le backend (`detail`) UNIQUEMENT
 *      s'il est sûr (français, lisible) ;
 *   3. retombe sinon sur un message de repli propre.
 */

export const GENERIC_ERROR_MESSAGE =
  'Une erreur est survenue. Réessayez dans quelques instants.';
export const NETWORK_ERROR_MESSAGE =
  'Connexion impossible. Vérifiez votre connexion internet.';
export const SERVER_ERROR_MESSAGE =
  'Le service rencontre un problème. Réessayez dans quelques instants.';
export const SERVICE_UNAVAILABLE_MESSAGE =
  'Service temporairement indisponible. Réessayez dans quelques secondes.';
export const UNAUTHORIZED_MESSAGE =
  'Vous n’avez pas les droits nécessaires pour cette action.';

/**
 * Motifs qui révèlent un message destiné aux développeurs : on ne les affiche
 * jamais tels quels. La liste est volontairement large (insensible à la casse).
 */
const TECHNICAL_PATTERNS: RegExp[] = [
  /internal server error/i,
  /\btraceback\b/i,
  /\bexception\b/i,
  /\.py\b/i,
  /openrouter/i,
  /\bstr\s*\(/i,
  /nonetype/i,
  /\b(key|value|type|index|attribute|runtime)error\b/i,
  /psycopg|sqlalchemy|asyncpg|supabase/i,
  /request failed with status/i,
  /network error/i,
  /timeout of \d+ms/i,
  /econnrefused|econnreset|enotfound|etimedout/i,
  /<class\b|<module\b/i,
  /cannot read propert/i,
  /(undefined|null) is not/i,
  /is not a function/i,
  /\[object object\]/i,
  /500 internal|502 bad gateway|503 service|504 gateway/i,
  /\bnull\b.*\bnull\b/i,
  /migration|alembic|relation .* does not exist/i,
];

/** Indique si un texte ressemble à un message technique (non destiné à l'utilisateur). */
export function looksTechnical(message: string): boolean {
  const trimmed = message.trim();
  if (!trimmed) return true;
  return TECHNICAL_PATTERNS.some((re) => re.test(trimmed));
}

/**
 * Nettoie un message métier renvoyé par le backend.
 * Renvoie le message si on peut le montrer à l'utilisateur, sinon `null`.
 */
export function sanitizeBackendMessage(
  message: string | null | undefined,
): string | null {
  if (typeof message !== 'string') return null;
  let cleaned = message.trim();
  if (!cleaned) return null;
  // Retire des préfixes/symboles techniques courants.
  cleaned = cleaned.replace(/^\[ERREUR\]\s*/i, '').replace(/^❌\s*/, '').trim();
  if (!cleaned) return null;
  if (looksTechnical(cleaned)) return null;
  // Tronque les pavés trop longs (logs concaténés).
  return cleaned.length > 220 ? `${cleaned.slice(0, 220)}…` : cleaned;
}

/** Récupère le code HTTP d'une erreur, si disponible. */
export function getApiErrorStatus(error: unknown): number | undefined {
  if (axios.isAxiosError(error)) return error.response?.status;
  if (error && typeof error === 'object' && 'response' in error) {
    const res = (error as { response?: { status?: number } }).response;
    return res?.status;
  }
  return undefined;
}

function extractDetail(error: unknown): string | null {
  let data: unknown;
  if (axios.isAxiosError(error)) {
    data = error.response?.data;
  } else if (error && typeof error === 'object' && 'response' in error) {
    data = (error as { response?: { data?: unknown } }).response?.data;
  }
  if (!data || typeof data !== 'object') return null;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;
  // Erreurs de validation FastAPI : detail = [{ msg, loc, ... }]
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: unknown } | undefined;
    if (first && typeof first.msg === 'string') return first.msg;
  }
  // Le backend renvoie parfois un objet (ex. alertes bulletin) : non affichable ici.
  return null;
}

/**
 * Point d'entrée unique : transforme n'importe quelle erreur en message clair,
 * en français, et sans fuite technique.
 *
 * @param error    L'erreur capturée (Axios, Error, inconnue…).
 * @param fallback Message métier de repli (doit déjà être clair et en français).
 */
/** Message de repli pour l'échec de génération d'un bulletin de paie. */
export const PAYROLL_GENERATION_FALLBACK =
  'Impossible de générer le bulletin. Vérifiez la fiche du collaborateur (contrat, planning du mois, saisies variables).';

/**
 * Message d'échec de génération de paie : privilégie le détail métier renvoyé par
 * l'API (même en 500 si le texte est lisible), puis retombe sur getUserErrorMessage.
 */
export function getPayrollGenerationErrorMessage(error: unknown): string {
  const detail = sanitizeBackendMessage(extractDetail(error));
  if (detail) return detail;
  return getUserErrorMessage(error, PAYROLL_GENERATION_FALLBACK);
}

export function getUserErrorMessage(
  error: unknown,
  fallback: string = GENERIC_ERROR_MESSAGE,
): string {
  const status = getApiErrorStatus(error);

  // Erreur réseau (pas de réponse du serveur).
  if (axios.isAxiosError(error) && !error.response) {
    return NETWORK_ERROR_MESSAGE;
  }

  if (status === 401 || status === 403) {
    const detail = sanitizeBackendMessage(extractDetail(error));
    return detail ?? UNAUTHORIZED_MESSAGE;
  }

  if (status === 503) return SERVICE_UNAVAILABLE_MESSAGE;
  if (status !== undefined && status >= 500) return SERVER_ERROR_MESSAGE;

  // Message métier du backend, s'il est sûr.
  const detail = sanitizeBackendMessage(extractDetail(error));
  if (detail) return detail;

  // On n'expose jamais `error.message` brut (souvent technique / anglais).
  return fallback;
}

type ErrorToastOptions = {
  /** Titre du toast. Défaut : « Une erreur est survenue ». */
  title?: string;
  /** Message de repli métier passé à `getUserErrorMessage`. */
  fallback?: string;
};

/**
 * Affiche un toast d'erreur normalisé à partir de n'importe quelle erreur.
 * Remplace les `alert()` et les `toast({ variant: 'destructive', ... })` ad hoc.
 */
export function showErrorToast(error: unknown, options: ErrorToastOptions = {}) {
  const { title = 'Une erreur est survenue', fallback } = options;
  return toast({
    variant: 'destructive',
    title,
    description: getUserErrorMessage(error, fallback ?? GENERIC_ERROR_MESSAGE),
  });
}
