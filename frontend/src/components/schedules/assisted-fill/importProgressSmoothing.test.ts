import { describe, expect, it } from 'vitest';

import {
  expectedSegmentMs,
  smoothedPercent,
} from './importProgressSmoothing';

describe('smoothedPercent', () => {
  it('part du plancher réel à t=0', () => {
    expect(smoothedPercent({ floorPct: 0, elapsedMs: 0, expectedMs: 12000 })).toBe(0);
    expect(smoothedPercent({ floorPct: 40, elapsedMs: 0, expectedMs: 12000 })).toBe(40);
  });

  it('est strictement croissant dans un segment', () => {
    let prev = -1;
    for (const t of [0, 500, 2000, 6000, 12000, 30000]) {
      const v = smoothedPercent({ floorPct: 0, elapsedMs: t, expectedMs: 12000 });
      expect(v).toBeGreaterThanOrEqual(prev);
      prev = v;
    }
  });

  it("ne ment jamais : reste sous 90 % de l'espace restant", () => {
    const vFromZero = smoothedPercent({ floorPct: 0, elapsedMs: 600000, expectedMs: 12000 });
    expect(vFromZero).toBeLessThan(90);
    const vFromHalf = smoothedPercent({ floorPct: 50, elapsedMs: 600000, expectedMs: 12000 });
    expect(vFromHalf).toBeLessThan(50 + 0.9 * 50);
  });

  it('a bien progressé à la durée attendue (le zerma est visible)', () => {
    const v = smoothedPercent({ floorPct: 0, elapsedMs: 12000, expectedMs: 12000 });
    expect(v).toBeGreaterThan(55);
  });

  it('un plancher à 100 reste à 100', () => {
    expect(smoothedPercent({ floorPct: 100, elapsedMs: 5000, expectedMs: 12000 })).toBe(100);
  });
});

describe('expectedSegmentMs', () => {
  it("échelonne la durée attendue sur les pages restantes", () => {
    expect(expectedSegmentMs(0, 1)).toBe(12000);
    expect(expectedSegmentMs(0, 4)).toBe(48000);
    expect(expectedSegmentMs(3, 4)).toBe(12000);
  });

  it('reste utilisable sans total connu', () => {
    expect(expectedSegmentMs(0, 0)).toBe(12000);
  });
});
