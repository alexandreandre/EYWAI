import type { AppUserRole } from '@/lib/userRoleLabels';
import { isPlatformAdmin, type PlatformAdminUser } from '@/lib/platformAdmin';

type PostLoginUser = PlatformAdminUser & {
  role?: AppUserRole;
};

/** Chemins réservés à l'espace collaborateur (absents des routes RH). */
const EMPLOYEE_ONLY_PREFIXES = [
  '/profile',
  '/payslips',
  '/badgeuse',
  '/calendar',
  '/absences',
  '/employee/formation',
  '/employee/planning',
  '/employee/documents',
  '/employee/onboarding',
  '/employee/payslips',
] as const;

export function safeReturnPath(pathname: string | undefined): string {
  if (!pathname || pathname === '/login' || pathname.startsWith('/login?')) {
    return '/';
  }
  return pathname;
}

export function isEmployeeOnlyPath(pathname: string): boolean {
  return EMPLOYEE_ONLY_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

function readCollaborateurRhViewMode(): 'rh' | 'collaborateur' {
  const saved = localStorage.getItem('collaborateur_rh_view_mode');
  return saved === 'collaborateur' ? 'collaborateur' : 'rh';
}

function usesEmployeeRoutes(user: PostLoginUser, viewMode?: 'rh' | 'collaborateur'): boolean {
  if (user.role === 'collaborateur') {
    return true;
  }
  if (user.role === 'collaborateur_rh') {
    const mode = viewMode ?? readCollaborateurRhViewMode();
    return mode === 'collaborateur';
  }
  return false;
}

/**
 * Après connexion ou changement de rôle, évite de renvoyer vers une route
 * inaccessible (ex. espace employé → compte RH sur /calendar).
 */
export function resolvePostLoginPath(
  fromPathname: string | undefined,
  user: PostLoginUser,
  viewMode?: 'rh' | 'collaborateur',
): string {
  const path = safeReturnPath(fromPathname);
  if (path === '/') {
    return '/';
  }

  if (usesEmployeeRoutes(user, viewMode)) {
    return path;
  }

  if (isPlatformAdmin(user) && path.startsWith('/super-admin')) {
    return path;
  }

  if (isEmployeeOnlyPath(path)) {
    return '/';
  }

  return path;
}
