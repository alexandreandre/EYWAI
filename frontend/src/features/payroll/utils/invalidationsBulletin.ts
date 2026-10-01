/**
 * Ce qu'un bulletin généré, régénéré ou supprimé rend périmé à l'écran.
 *
 * Le 29/09, après une suppression puis une régénération, la paie du mois
 * montrait encore l'ancien bulletin : seule la liste du salarié était
 * invalidée, et pas toujours. Les trois actions passent désormais ici.
 */

import type { QueryClient, QueryKey } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';

/** Paie du mois : le contrôle avant paie, tous mois de la société. */
export function clesDeLaPaieDuMois(companyId: string | undefined): QueryKey[] {
  return [queryKeys.payrollPreflightTousMois(companyId)];
}

/**
 * Ce qui entoure les bulletins de la société : onglets d'un bulletin
 * (comparaison N-1 et tendance lisent aussi les mois voisins), anomalies des
 * bulletins, explorateur de documents, paie du mois.
 */
export function clesAutourDesBulletins(companyId: string | undefined): QueryKey[] {
  return [
    queryKeys.payslipComparisonTous(),
    queryKeys.payslipTrendTous(),
    queryKeys.payslipsAnomaliesTousMois(companyId),
    queryKeys.documentsExplorer(companyId),
    ...clesDeLaPaieDuMois(companyId),
  ];
}

/** La liste des bulletins du salarié (paie du mois, fiche salarié), puis ce qui l'entoure. */
export function clesAInvaliderApresBulletin(
  companyId: string | undefined,
  employeeId: string
): QueryKey[] {
  return [queryKeys.employeePayslips(companyId, employeeId), ...clesAutourDesBulletins(companyId)];
}

/** Une liste de bulletins d'un salarié de la société, quel qu'il soit. */
function estUneListeDeBulletins(queryKey: QueryKey, companyId: string | undefined): boolean {
  const employeeId = queryKey[3];
  if (typeof employeeId !== 'string') return false;
  const liste = queryKeys.employeePayslips(companyId, employeeId);
  return queryKey.length === liste.length && liste.every((segment, i) => queryKey[i] === segment);
}

/** Invalide ces clés ; rend la main une fois les requêtes affichées rechargées. */
export async function invaliderCles(queryClient: QueryClient, cles: readonly QueryKey[]): Promise<void> {
  await Promise.all(cles.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
}

/**
 * Après une génération, une régénération ou une suppression. Sans salarié
 * connu (bulletin introuvable), toutes les listes de bulletins de la société.
 */
export async function invaliderApresBulletin(
  queryClient: QueryClient,
  companyId: string | undefined,
  employeeId: string | undefined
): Promise<void> {
  if (employeeId) {
    await invaliderCles(queryClient, clesAInvaliderApresBulletin(companyId, employeeId));
    return;
  }
  await Promise.all([
    queryClient.invalidateQueries({
      predicate: (query) => estUneListeDeBulletins(query.queryKey, companyId),
    }),
    invaliderCles(queryClient, clesAutourDesBulletins(companyId)),
  ]);
}
