import { describe, expect, it } from 'vitest';
import { hasCachedTextSource } from './collectiveAgreementRulesPdf';

describe('hasCachedTextSource', () => {
  it('accepte kali, text et pdf', () => {
    expect(hasCachedTextSource('kali')).toBe(true);
    expect(hasCachedTextSource('text')).toBe(true);
    expect(hasCachedTextSource('pdf')).toBe(true);
  });

  it('refuse les sources absentes ou inconnues', () => {
    expect(hasCachedTextSource(null)).toBe(false);
    expect(hasCachedTextSource(undefined)).toBe(false);
    expect(hasCachedTextSource('')).toBe(false);
    expect(hasCachedTextSource('unknown')).toBe(false);
  });
});
