import { statusLabels, type ExitStatus } from '@/api/employeeExits';

function jourLocal(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const jj = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${jj}`;
}

/**
 * Libellé du statut d'un départ. Une fin de CDD, une retraite ou une fin de
 * période d'essai naît au statut « effective » : avant le dernier jour
 * travaillé, l'écran dit « Prévu le … » plutôt qu'« Effective » (recette 02/10).
 */
export function libelleStatutDepart(
  statut: ExitStatus,
  dernierJour: string | null | undefined,
  aujourdHui: Date = new Date()
): string {
  const jour = (dernierJour ?? '').slice(0, 10);
  if (statut.endsWith('_effective') && /^\d{4}-\d{2}-\d{2}$/.test(jour) && jour > jourLocal(aujourdHui)) {
    const [a, m, j] = jour.split('-');
    return `Prévu le ${j}/${m}/${a}`;
  }
  return statusLabels[statut] ?? statut;
}
