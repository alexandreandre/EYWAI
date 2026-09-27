import { describe, expect, it } from 'vitest';
import { estRoleRh } from './rolesRh';

describe('estRoleRh', () => {
  it('administrateur, RH et collaborateur RH modifient comme un RH', () => {
    expect(estRoleRh('admin')).toBe(true);
    expect(estRoleRh('rh')).toBe(true);
    expect(estRoleRh('collaborateur_rh')).toBe(true);
  });

  it('un collaborateur, un rôle inconnu ou absent, non', () => {
    expect(estRoleRh('collaborateur')).toBe(false);
    expect(estRoleRh('custom')).toBe(false);
    expect(estRoleRh(undefined)).toBe(false);
    expect(estRoleRh(null)).toBe(false);
  });
});
