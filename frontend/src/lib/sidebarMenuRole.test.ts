import { describe, expect, it } from 'vitest';

import { resolveSidebarMenuKey } from './sidebarMenuRole';

describe('resolveSidebarMenuKey', () => {
  it('ouvre le menu manager pour un rôle custom (directeurs)', () => {
    expect(resolveSidebarMenuKey('custom')).toBe('manager');
  });

  it('ouvre le menu RH pour un administrateur société', () => {
    expect(resolveSidebarMenuKey('admin')).toBe('rh');
  });

  it('ouvre le menu RH pour un rôle rh', () => {
    expect(resolveSidebarMenuKey('rh')).toBe('rh');
  });

  it('ouvre le menu RH pour un collaborateur_rh en vue RH', () => {
    expect(resolveSidebarMenuKey('collaborateur_rh', 'rh')).toBe('rh');
  });

  it('ouvre le menu salarié pour un collaborateur_rh en vue collaborateur', () => {
    expect(resolveSidebarMenuKey('collaborateur_rh', 'collaborateur')).toBe(
      'employee',
    );
  });

  it("n'ouvre pas cette sidebar pour un collaborateur (layout salarié)", () => {
    expect(resolveSidebarMenuKey('collaborateur')).toBeNull();
  });

  it("n'ouvre aucun menu pour un rôle inconnu", () => {
    expect(resolveSidebarMenuKey('inconnu')).toBeNull();
    expect(resolveSidebarMenuKey(undefined)).toBeNull();
  });
});
