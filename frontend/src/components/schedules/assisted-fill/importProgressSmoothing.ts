/**
 * Lissage de la barre de progression de l'import de pointages.
 *
 * Les événements réels du job (pages_done/pages_total) n'arrivent que par
 * page ou par lot : sur un PDF d'une page, la barre passait de vide à pleine.
 * Entre deux événements réels, la barre avance en simulé : montée rapide puis
 * ralentissement asymptotique, plafonnée sous 90 % de l'espace restant — elle
 * n'affiche jamais un faux « terminé ». Chaque événement réel ré-ancre le
 * plancher, la complétion réelle amène à 100 %.
 */

/** Durée typique d'extraction d'une page côté backend (mesurée ~12 s). */
const PAGE_EXPECTED_MS = 12000;

/** Part de l'espace restant que le simulé peut consommer (jamais 100 %). */
const CEILING_RATIO = 0.9;

/**
 * Valeur lissée (0-100) : plancher réel + progression asymptotique vers
 * `floor + 90 % du restant`, strictement croissante dans un segment.
 */
export function smoothedPercent({
  floorPct,
  elapsedMs,
  expectedMs,
}: {
  floorPct: number;
  elapsedMs: number;
  expectedMs: number;
}): number {
  const floor = Math.min(100, Math.max(0, floorPct));
  const span = (100 - floor) * CEILING_RATIO;
  if (span <= 0) return floor;
  const tau = Math.max(1, expectedMs) / 2.2;
  // min(…, 0.999) : en flottant l'exponentielle sature à 0 sur un long
  // segment, et la barre toucherait exactement le plafond — jamais.
  const ratio = Math.min(0.999, 1 - Math.exp(-Math.max(0, elapsedMs) / tau));
  return floor + span * ratio;
}

/**
 * Durée attendue du segment courant : proportionnelle aux pages restantes
 * (un lot de 4 pages met ~4× plus longtemps qu'une page à produire son
 * prochain événement réel). Sans total connu, on suppose une page.
 */
export function expectedSegmentMs(pagesDone: number, pagesTotal: number): number {
  const remaining = Math.max(1, pagesTotal - pagesDone);
  return remaining * PAGE_EXPECTED_MS;
}
