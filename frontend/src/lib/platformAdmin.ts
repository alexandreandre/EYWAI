/**
 * Administrateurs plateforme EYWAI (accès Administration + RH complet).
 */

export type PlatformAdminUser = {
  is_platform_admin?: boolean;
  /** @deprecated compat API — préférer is_platform_admin */
  is_super_admin?: boolean;
  role?: string;
};

export function isPlatformAdmin(user: PlatformAdminUser | null | undefined): boolean {
  if (!user) return false;
  return Boolean(user.is_platform_admin || user.is_super_admin);
}

/** Rôle effectif côté RH : admin plateforme = admin entreprise. */
export function effectiveRhRole(user: PlatformAdminUser | null | undefined): string | undefined {
  if (!user) return undefined;
  if (isPlatformAdmin(user)) return 'admin';
  return user.role;
}

export function hasFullRhAccess(user: PlatformAdminUser | null | undefined): boolean {
  if (!user) return false;
  if (isPlatformAdmin(user)) return true;
  const role = user.role;
  return role === 'admin' || role === 'rh' || role === 'collaborateur_rh';
}
