import type { CompanySettingsResponse, IndemniteCpFinCddMethode } from '@/api/company';

export const METHODE_PAR_DEFAUT: IndemniteCpFinCddMethode = 'remuneration_versee';

export const METHODES_INDEMNITE_CP_FIN_CDD: ReadonlyArray<{
  valeur: IndemniteCpFinCddMethode;
  libelle: string;
  description: string;
}> = [
  {
    valeur: 'remuneration_versee',
    libelle: 'Rémunération réellement versée',
    description:
      'Dixième du brut perçu pendant le contrat, précarité comprise. Règle légale, valeur par défaut.',
  },
  {
    valeur: 'salaire_retabli_solde_n1',
    libelle: 'Salaire rétabli du mois de sortie, congés N-1 inclus',
    description:
      'Dixième calculé comme si le dernier mois avait été complet, précarité comprise, en ajoutant le solde de congés N-1 valorisé au maintien de salaire. Le bulletin détaille l’assiette.',
  },
];

/** Absente ou inconnue, la méthode vaut la règle légale. */
export function lireMethodeIndemniteCpFinCdd(
  settings: CompanySettingsResponse | undefined
): IndemniteCpFinCddMethode {
  const brute = settings?.settings?.indemnite_cp_fin_cdd;
  return METHODES_INDEMNITE_CP_FIN_CDD.some((m) => m.valeur === brute)
    ? (brute as IndemniteCpFinCddMethode)
    : METHODE_PAR_DEFAUT;
}
