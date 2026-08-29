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

/** Les 14 entrées de menu conservées en mode paie. */
export const PAYROLL_FOCUS_NAV_URLS: readonly string[] = [
  '/',
  '/employees',
  '/schedules',
  '/leaves',
  '/suivi-temps-travail',
  '/expenses',
  '/saisies',
  '/salary-seizures',
  '/salary-advances',
  '/simulation',
  '/rates',
  '/taux-pas',
  '/exports',
  '/payroll',
];

/**
 * Routes atteignables sans figurer dans le menu RH.
 *
 * - `/payslips` : édition d'un bulletin. `/employees/:id` et `/payroll/:id`
 *   sont déjà couvertes par le préfixe de leur entrée de menu, pas celle-ci.
 * - Les files de validation manager sont le transport d'actions qui sont, elles,
 *   dans le périmètre : valider un bulletin, approuver une note de frais ou une
 *   avance. Les couper reviendrait à priver les directeurs de leur seul rôle.
 *   Elles vivent dans `menuItems.manager` et ne remontent donc pas dans le menu RH.
 */
const PAYROLL_FOCUS_EXTRA_PREFIXES: readonly string[] = [
  '/payslips',
  '/approvals',
  '/leave-requests',
  '/cet-requests',
  // Anciennes entrées de menu devenues de pures redirections vers
  // /suivi-temps-travail : atteignables pour que les liens directs
  // continuent de rediriger, absentes du menu.
  '/suivi-contingent-hs',
  '/suivi-modulation',
  // Aucun mouvement CET ni prêt employeur dans le groupe pour l'instant :
  // hors menu en mode paie, mais les routes restent atteignables.
  '/suivi-cet',
  '/employee-loans',
];

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
  // Filtre sur la liste des entrées de MENU, pas sur l'atteignabilité :
  // une route peut rester atteignable (EXTRA_PREFIXES) sans être affichée.
  const keep = (item: TItem) =>
    section === 'team'
      ? item.url === '/employees'
      : PAYROLL_FOCUS_NAV_URLS.includes(item.url);
  return groups
    .map((group) => ({ ...group, items: group.items.filter(keep) }))
    .filter((group) => group.items.length > 0);
}
