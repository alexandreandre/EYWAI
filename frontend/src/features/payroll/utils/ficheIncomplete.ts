import type { PayrollGenerateEmployee } from '@/features/payroll/types';

/** Les champs que le serveur dit manquants ; vide s'il n'en renvoie pas (on n'invente rien). */
export function champsManquants(emp: Pick<PayrollGenerateEmployee, 'missing_payroll_fields'>): string[] {
  return emp.missing_payroll_fields?.filter(Boolean) ?? [];
}

/**
 * Titre et description quand aucun salarié n'est sélectionnable alors que des
 * salariés actifs existent : fiche à compléter, ou simplement hors période du
 * mois choisi (fiche complète que le contrat ne couvre pas).
 */
export function messageAucunSelectionnable(
  salaries: ReadonlyArray<Pick<PayrollGenerateEmployee, 'payroll_eligible' | 'missing_payroll_fields'>>,
): { titre: string; description: string; fichesACompleter: boolean } {
  const n = salaries.length;
  const nom = `${n} collaborateur${n > 1 ? 's' : ''}`;
  const fichesACompleter = salaries.some(
    (s) => s.payroll_eligible === false || champsManquants(s).length > 0,
  );
  if (fichesACompleter) {
    return {
      titre: `${nom} — fiche${n > 1 ? 's' : ''} à compléter`,
      description:
        'Des collaborateurs sont présents, mais leurs fiches paie doivent être finalisées avant la génération.',
      fichesACompleter,
    };
  }
  return {
    titre: `${nom} — aucun présent sur le mois choisi`,
    description:
      'Leur fiche est complète, mais leur contrat ne couvre pas ce mois : choisissez un autre mois ou vérifiez leurs dates d’entrée et de sortie.',
    fichesACompleter,
  };
}
