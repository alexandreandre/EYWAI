import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Environnement des tests E2E : URLs cibles, session d'auth, garde anti-prod.
 * Seul module à lire .env.e2e — la config et les specs importent d'ici.
 */

const repertoireFrontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

// Charge .env.e2e sans dépendance externe (les variables déjà présentes gagnent).
const fichierEnv = path.join(repertoireFrontend, '.env.e2e');
if (fs.existsSync(fichierEnv)) {
  for (const ligne of fs.readFileSync(fichierEnv, 'utf8').split('\n')) {
    const m = ligne.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/);
    if (!m || process.env[m[1]] !== undefined) continue;
    let valeur = m[2].replace(/\r$/, '').trim();
    if (
      (valeur.startsWith('"') && valeur.endsWith('"')) ||
      (valeur.startsWith("'") && valeur.endsWith("'"))
    ) {
      valeur = valeur.slice(1, -1);
    }
    process.env[m[1]] = valeur;
  }
}

export const URL_FRONT_TEST = 'https://sirh-frontend-test-505040845625.europe-west1.run.app';
export const URL_BACK_TEST = 'https://sirh-backend-test-505040845625.europe-west1.run.app';

export const BASE_URL = process.env.E2E_BASE_URL ?? URL_FRONT_TEST;
export const API_URL = process.env.E2E_API_URL ?? URL_BACK_TEST;

// Garde anti-prod en ALLOWLIST : tout hôte non listé est refusé — un domaine
// custom, l'URL Cloud Run héritée (<service>-<hash>-ew.a.run.app) ou une faute
// de frappe ne passeront pas. Les données de prod sont réelles.
const HOTES_AUTORISES = new Set([
  new URL(URL_FRONT_TEST).hostname,
  new URL(URL_BACK_TEST).hostname,
  'localhost',
  '127.0.0.1',
]);
for (const [nom, url] of [
  ['E2E_BASE_URL', BASE_URL],
  ['E2E_API_URL', API_URL],
] as const) {
  const hote = new URL(url).hostname.toLowerCase();
  if (!HOTES_AUTORISES.has(hote)) {
    throw new Error(
      `${nom}=${url} refusé : hôte hors allowlist (env de test ou localhost uniquement). ` +
        'Les E2E ne tournent JAMAIS contre la production.',
    );
  }
}

export const ETAT_AUTH = path.join(repertoireFrontend, 'e2e', '.auth', 'qa.json');

export const identifiantsPresents = Boolean(
  process.env.E2E_QA_EMAIL && process.env.E2E_QA_PASSWORD,
);
