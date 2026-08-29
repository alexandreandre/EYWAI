export type AiFillStep = {
  label: string;
  threshold: number;
};

export type AiFillStepState = 'pending' | 'active' | 'done';

/** Plafond visuel : la barre ne doit jamais suggérer que l’analyse est terminée. */
const ASYMPTOTE = 90;
const CAP = 89.999;
/** Contrôle la montée rapide puis le ralentissement (1 − e^{−k t/T}). */
const RISE = 1.6;

export const AI_FILL_STEPS: readonly AiFillStep[] = [
  { label: 'Lecture de la consigne…', threshold: 0 },
  { label: 'Reconnaissance des collaborateurs…', threshold: 22 },
  { label: 'Construction des horaires…', threshold: 48 },
  { label: 'Vérification des totaux…', threshold: 72 },
];

/**
 * Progression asymptotique 0 → (sous 90) selon le temps écoulé / durée attendue.
 * Strictement croissante, jamais 100 — le vrai 100 n’existe qu’à la fin réelle.
 */
export function progressAt(elapsedMs: number, expectedMs: number): number {
  if (elapsedMs <= 0 || !(expectedMs > 0)) return 0;
  const ratio = elapsedMs / expectedMs;
  const value = ASYMPTOTE * (1 - Math.exp(-RISE * ratio));
  return Math.min(value, CAP);
}

export function stepStateAt(progress: number, index: number): AiFillStepState {
  const step = AI_FILL_STEPS[index];
  if (!step) return 'pending';
  if (progress < step.threshold) return 'pending';
  const next = AI_FILL_STEPS[index + 1];
  if (next && progress >= next.threshold) return 'done';
  return 'active';
}
