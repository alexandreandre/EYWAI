import { expect, type Page } from '@playwright/test';

/**
 * Collecte les erreurs console, requêtes échouées et réponses 5xx d'une page.
 * Chaque spec appelle `surveiller(page)` en début de test puis
 * `verifierPageSaine(page, s)` en fin de parcours : un écran « qui s'affiche »
 * mais qui crache des erreurs est un écran cassé.
 */

// Bruit connu, sans valeur de diagnostic — à garder COURT et justifié.
const BRUIT: RegExp[] = [
  /favicon/i,
  /net::ERR_ABORTED/i, // requêtes annulées par une navigation (comportement normal des SPA)
  /ResizeObserver loop/i,
  /Download the React DevTools/i,
  // Constats data/qa/constats/2026-08-12.md #2 et #3 — 404 « by design » de
  // /leaves. Allowlistés NOMMÉMENT : tout autre 404 reste une erreur.
  /status of 404 .*\/api\/employees\/me\]/,
  /status of 404 .*\/api\/absences\/[^/\]]+\/certificate\]/,
];

// Texte exact de src/components/ErrorBoundary.tsx (apostrophe droite) ; le
// `.` couvre aussi la variante typographique si le libellé évolue.
const TEXTE_CRASH = /Une erreur s.est produite/;

export type Surveillance = { erreurs: string[] };

// Les URLs sont tronquées à leur chemin : pas de query string (jetons, filtres
// nominatifs…) dans des messages d'échec qui finissent dans des logs CI publics.
function sansQuery(url: string): string {
  const i = url.indexOf('?');
  return i === -1 ? url : `${url.slice(0, i)}?…`;
}

export function surveiller(page: Page): Surveillance {
  const s: Surveillance = { erreurs: [] };
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    // « Failed to load resource » n'inclut pas l'URL dans le texte : elle est
    // dans location(). On la garde (sans query) pour un diagnostic utile.
    const ou = msg.location().url ? ` [${sansQuery(msg.location().url)}]` : '';
    s.erreurs.push(`console: ${msg.text()}${ou}`);
  });
  page.on('pageerror', (err) => {
    s.erreurs.push(`exception: ${err.message}`);
  });
  page.on('requestfailed', (req) => {
    s.erreurs.push(`échec réseau: ${req.method()} ${sansQuery(req.url())} — ${req.failure()?.errorText}`);
  });
  page.on('response', (rep) => {
    if (rep.status() >= 500) s.erreurs.push(`HTTP ${rep.status()}: ${sansQuery(rep.url())}`);
  });
  return s;
}

export function erreursSerieuses(s: Surveillance): string[] {
  return s.erreurs.filter((e) => !BRUIT.some((re) => re.test(e)));
}

/**
 * À appeler en FIN de test : attend que le réseau se calme, puis vérifie
 * l'absence d'ErrorBoundary et d'erreurs console/réseau. L'ordre compte —
 * vérifier le crash avant la fin du rendu laisserait passer un ErrorBoundary
 * affiché juste après.
 */
export async function verifierPageSaine(page: Page, s: Surveillance, contexte = ''): Promise<void> {
  await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
  await expect(page.getByText(TEXTE_CRASH)).toHaveCount(0);
  expect(erreursSerieuses(s), contexte).toEqual([]);
}
