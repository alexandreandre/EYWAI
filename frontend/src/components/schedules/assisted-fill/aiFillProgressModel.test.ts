import { describe, expect, it } from 'vitest';
import {
  AI_FILL_STEPS,
  progressAt,
  stepStateAt,
} from './aiFillProgressModel';

const EXPECTED_MS = 18_000;

describe('progressAt', () => {
  it('est nulle à t = 0', () => {
    expect(progressAt(0, EXPECTED_MS)).toBe(0);
  });

  it('est strictement croissante', () => {
    const samples = [0, 200, 1_000, 4_500, 9_000, 18_000, 36_000, 90_000];
    for (let i = 1; i < samples.length; i += 1) {
      expect(progressAt(samples[i], EXPECTED_MS)).toBeGreaterThan(
        progressAt(samples[i - 1], EXPECTED_MS),
      );
    }
  });

  it('monte plus vite au début puis ralentit', () => {
    const early = progressAt(EXPECTED_MS / 2, EXPECTED_MS) - progressAt(0, EXPECTED_MS);
    const late =
      progressAt(EXPECTED_MS, EXPECTED_MS) - progressAt(EXPECTED_MS / 2, EXPECTED_MS);
    expect(early).toBeGreaterThan(late);
  });

  it('reste strictement sous 90 même après un délai très long', () => {
    expect(progressAt(EXPECTED_MS * 50, EXPECTED_MS)).toBeLessThan(90);
    expect(progressAt(1e12, EXPECTED_MS)).toBeLessThan(90);
    expect(progressAt(1e12, EXPECTED_MS)).toBeGreaterThan(80);
  });

  it('n’atteint jamais 100', () => {
    expect(progressAt(Number.MAX_SAFE_INTEGER, EXPECTED_MS)).toBeLessThan(90);
  });
});

describe('AI_FILL_STEPS', () => {
  it('expose 4 étapes aux seuils croissants sous 90', () => {
    expect(AI_FILL_STEPS).toHaveLength(4);
    expect(AI_FILL_STEPS.map((s) => s.label)).toEqual([
      'Lecture de la consigne…',
      'Reconnaissance des collaborateurs…',
      'Construction des horaires…',
      'Vérification des totaux…',
    ]);
    const thresholds = AI_FILL_STEPS.map((s) => s.threshold);
    expect(thresholds[0]).toBe(0);
    expect(thresholds[1]).toBeGreaterThanOrEqual(20);
    expect(thresholds[1]).toBeLessThanOrEqual(24);
    expect(thresholds[2]).toBeGreaterThanOrEqual(46);
    expect(thresholds[2]).toBeLessThanOrEqual(50);
    expect(thresholds[3]).toBeGreaterThanOrEqual(70);
    expect(thresholds[3]).toBeLessThanOrEqual(74);
    for (let i = 1; i < thresholds.length; i += 1) {
      expect(thresholds[i]).toBeGreaterThan(thresholds[i - 1]);
    }
    expect(Math.max(...thresholds)).toBeLessThan(90);
  });
});

describe('stepStateAt', () => {
  it('marque la première étape active et les suivantes en attente à 0 %', () => {
    expect(stepStateAt(0, 0)).toBe('active');
    expect(stepStateAt(0, 1)).toBe('pending');
    expect(stepStateAt(0, 2)).toBe('pending');
    expect(stepStateAt(0, 3)).toBe('pending');
  });

  it('passe l’étape précédente en done et l’étape courante en active aux bornes', () => {
    const t1 = AI_FILL_STEPS[1].threshold;
    expect(stepStateAt(t1 - 0.01, 0)).toBe('active');
    expect(stepStateAt(t1 - 0.01, 1)).toBe('pending');
    expect(stepStateAt(t1, 0)).toBe('done');
    expect(stepStateAt(t1, 1)).toBe('active');
    expect(stepStateAt(t1, 2)).toBe('pending');

    const t2 = AI_FILL_STEPS[2].threshold;
    expect(stepStateAt(t2, 0)).toBe('done');
    expect(stepStateAt(t2, 1)).toBe('done');
    expect(stepStateAt(t2, 2)).toBe('active');
    expect(stepStateAt(t2, 3)).toBe('pending');

    const t3 = AI_FILL_STEPS[3].threshold;
    expect(stepStateAt(t3, 0)).toBe('done');
    expect(stepStateAt(t3, 1)).toBe('done');
    expect(stepStateAt(t3, 2)).toBe('done');
    expect(stepStateAt(t3, 3)).toBe('active');
  });

  it('laisse la dernière étape active sous le plafond (jamais done à 89)', () => {
    expect(stepStateAt(89, 3)).toBe('active');
    expect(stepStateAt(89, 2)).toBe('done');
  });
});
