import { describe, expect, it } from 'vitest';
import { bicFieldSchema } from './ibanSchema';

describe('bicFieldSchema', () => {
  it('accepts an empty BIC', () => {
    expect(bicFieldSchema.parse('')).toBe('');
  });

  it('accepts 8 or 11 character BIC values', () => {
    expect(bicFieldSchema.safeParse('BNPAFRPP').success).toBe(true);
    expect(bicFieldSchema.safeParse('BNPAFRPPXXX').success).toBe(true);
  });

  it('rejects incomplete BIC values', () => {
    expect(bicFieldSchema.safeParse('BNPAFRP').success).toBe(false);
  });
});
