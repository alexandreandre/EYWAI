import { describe, expect, it } from 'vitest';
import { estBulletinImporte } from './bulletinImporte';

describe('estBulletinImporte', () => {
  it('reconnaît un bulletin repris à la bascule', () => {
    expect(estBulletinImporte({ origine: 'importe' })).toBe(true);
  });

  it('ne verrouille ni un bulletin calculé ni un bulletin sans origine', () => {
    expect(estBulletinImporte({ origine: 'calcule' })).toBe(false);
    expect(estBulletinImporte({})).toBe(false);
    expect(estBulletinImporte(undefined)).toBe(false);
  });
});
