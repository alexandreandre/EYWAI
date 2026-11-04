import { ToastAction, type ToastActionElement } from '@/components/ui/toast';
import { lienRecalculerMaintenant } from '@/features/payroll/utils/bulletinARecalculer';

/**
 * Le bouton « Recalculer maintenant » d'un message « bulletin à recalculer »
 * (audit R1, geste 3). `aller` est le `navigate` de l'écran appelant : le
 * message s'affiche hors du routeur.
 */
export function actionRecalculerMaintenant(
  cibles: ReadonlyArray<{ employee_id: string; year: number; month: number }> | null | undefined,
  aller: (lien: string) => void,
): ToastActionElement | undefined {
  const lien = lienRecalculerMaintenant(cibles);
  if (!lien) return undefined;
  return (
    <ToastAction altText="Recalculer maintenant les bulletins concernés" onClick={() => aller(lien)}>
      Recalculer maintenant
    </ToastAction>
  );
}
