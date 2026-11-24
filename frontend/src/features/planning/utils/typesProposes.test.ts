import { describe, expect, it } from 'vitest';

import type { ShiftType } from '@/api/planning';

import { typesProposesPourLeShift } from './typesProposes';

const matin: ShiftType = { id: 'a', code: 'MATIN', label: 'Matin', color: '#0f0' };
const nuitPartagee: ShiftType = {
  id: 'n',
  code: 'NUIT',
  label: 'Nuit',
  color: '#00f',
  allows_overnight: true,
};

describe('types proposés pour un shift', () => {
  it('le type d’un shift existant reste proposé même s’il n’est plus dans la liste', () => {
    // Poste de convention copié par la société, ou type désactivé : le shift
    // garde son type, et une nuit reste une nuit (fin avant début acceptée).
    const types = typesProposesPourLeShift([matin], nuitPartagee);
    expect(types.map((t) => t.id)).toEqual(['a', 'n']);
    expect(types[1].allows_overnight).toBe(true);
  });

  it('pas de doublon quand le type est déjà proposé', () => {
    expect(typesProposesPourLeShift([matin], matin)).toEqual([matin]);
  });

  it('sans shift : la liste telle quelle', () => {
    const liste = [matin];
    expect(typesProposesPourLeShift(liste, undefined)).toBe(liste);
  });
});
