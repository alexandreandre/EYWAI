import { isPayrollFocusAllowed } from '@/lib/payrollFocus';

/** Les pages RH fréquentes, préchargées après l'ouverture (hors chemin critique). */
export const PAGES_COURANTES = [
  '/',
  '/employees',
  '/employees/:id',
  '/leaves',
  '/planning',
  '/payroll',
  '/analytics',
] as const;

export type PageCourante = (typeof PAGES_COURANTES)[number];

/**
 * Seulement ce que la personne peut ouvrir : un collaborateur ne télécharge plus
 * les pages RH, le mode paie ne télécharge plus le planning ni les analyses
 * (audit R2 : `prefetchCommonChunks` préchargeait tout pour tout le monde).
 */
export function pagesCourantesAPrecharger({ rh, modePaie }: { rh: boolean; modePaie: boolean }): PageCourante[] {
  if (!rh) return [];
  return PAGES_COURANTES.filter((page) => !modePaie || isPayrollFocusAllowed(page.replace(':id', 'x')));
}
