import { exitTypeLabels, type ExitType } from '@/api/employeeExits';

/** Toast de succès après la création d'un départ : ce qui est créé, puis la suite. */
export function messageDepartCree(
  type: ExitType,
  dernierJour: string,
  nomSalarie?: string
): { title: string; description: string } {
  const [a, m, j] = dernierJour.slice(0, 10).split('-');
  const pour = nomSalarie ? ` pour ${nomSalarie}` : '';
  return {
    title: 'Départ créé',
    description: `${exitTypeLabels[type]}${pour}, dernier jour travaillé le ${j}/${m}/${a}. Prochaine étape : générer le bulletin de sortie dans la Paie.`,
  };
}
