/**
 * Mode paie — navigation réduite pendant la reprise client.
 *
 * Ne laisse accessible que la paie et ce dont la paie a besoin. S'applique à
 * tous les comptes client ; les administrateurs plateforme EYWAI conservent la
 * navigation complète.
 *
 * Spec : docs/superpowers/specs/2026-08-27-mode-paie-navigation-design.md
 */

import { isPlatformAdmin, type PlatformAdminUser } from '@/lib/platformAdmin';

/** Les 19 entrées de menu conservées en mode paie. */
export const PAYROLL_FOCUS_NAV_URLS: readonly string[] = [
  '/',
  '/employees',
  '/schedules',
  '/leaves',
  '/suivi-ijss',
  '/suivi-temps-travail',
  '/suivi-contingent-hs',
  '/suivi-modulation',
  '/suivi-cet',
  '/expenses',
  '/saisies',
  '/salary-seizures',
  '/salary-advances',
  '/employee-loans',
  '/simulation',
  '/rates',
  '/taux-pas',
  '/exports',
  '/payroll',
];

/**
 * Sous-routes atteignables depuis les écrans du périmètre mais absentes de la
 * navigation. `/employees/:id` et `/payroll/:id` sont déjà couvertes par le
 * préfixe de leur entrée de menu ; l'édition de bulletin ne l'est pas.
 */
const PAYROLL_FOCUS_EXTRA_PREFIXES: readonly string[] = ['/payslips'];

/** Comptes conservant la navigation complète en plus des admins plateforme. */
export const PAYROLL_FOCUS_BYPASS_EMAILS: readonly string[] = [
  'alexandreandre2004@gmail.com',
];

export type PayrollFocusUser = PlatformAdminUser & { email?: string };

function normalizePath(pathname: string): string {
  const path = pathname.split('?')[0].split('#')[0];
  return path.length > 1 && path.endsWith('/') ? path.slice(0, -1) : path;
}

/** Le chemin est-il atteignable quand le mode paie est actif ? */
export function isPayrollFocusAllowed(pathname: string): boolean {
  const path = normalizePath(pathname);
  if (path === '/') return true;
  return [...PAYROLL_FOCUS_NAV_URLS, ...PAYROLL_FOCUS_EXTRA_PREFIXES].some(
    (prefix) =>
      prefix !== '/' && (path === prefix || path.startsWith(`${prefix}/`)),
  );
}

/** Le mode paie s'applique-t-il à cet utilisateur ? */
export function isPayrollFocusActive(
  user: PayrollFocusUser | null | undefined,
): boolean {
  if (!user) return false;
  if (isPlatformAdmin(user)) return false;
  const email = user.email?.trim().toLowerCase();
  if (email && PAYROLL_FOCUS_BYPASS_EMAILS.includes(email)) return false;
  return true;
}

export type PayrollFocusSection = 'team' | 'gestion' | 'paie';

/**
 * Filtre une section de navigation. Le filtrage est par section et non par URL
 * seule : `/schedules` apparaît dans Gestion (« Calendriers ») et dans le
 * parcours paie (« Calendrier »), et seule la seconde doit survivre.
 */
export function restrictToPayrollFocus<
  TItem extends { url: string },
  TGroup extends { items: TItem[] },
>(section: PayrollFocusSection, groups: TGroup[]): TGroup[] {
  if (section === 'gestion') return [];
  const keep = (item: TItem) =>
    section === 'team' ? item.url === '/employees' : isPayrollFocusAllowed(item.url);
  return groups
    .map((group) => ({ ...group, items: group.items.filter(keep) }))
    .filter((group) => group.items.length > 0);
}
