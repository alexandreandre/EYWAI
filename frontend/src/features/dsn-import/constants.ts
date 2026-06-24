/** Libellés de secours si l'API ne fournit pas de hint. */
export const DSN_IMPORT_ISSUE_HINTS: Record<string, string> = {
  employee_other_company:
    "Ce salarié sera ignoré à la création ; ses cumuls seront ajoutés sur sa fiche existante.",
  target_siret_missing:
    "Renseignez le SIRET sur la fiche entreprise pour éviter les confusions futures.",
  duplicate_nir:
    "Ignorez ce salarié à l'import ou corrigez son rattachement entreprise.",
  employee_cross_company:
    "Passez l'action du salarié sur « Ignorer » ou corrigez sa fiche entreprise.",
  employee_not_found_cumul:
    "Vérifiez que le salarié est bien importé avant les cumuls du mois.",
  workforce_reconciliation_required:
    "Chaque écart effectif doit avoir une décision avant validation de l'import.",
  employee_new_hire_not_in_dsn:
    "Embauche récente absente de la DSN — normal si la première paie n'est pas encore dans le fichier. Confirmez pour poursuivre.",
  employee_missing_from_dsn:
    "Absent de la DSN du mois — clôturez le départ, ignorez si le fichier est incomplet, ou supprimez la fiche si elle est erronée.",
  employee_contract_end_in_dsn:
    "Une fin de contrat est indiquée dans la DSN — clôturez le départ ou ouvrez le parcours complet.",
  workforce_active_without_nir:
    "Ces salariés n'ont pas de NIR : la comparaison automatique avec la DSN est impossible.",
  payroll_field_conflict:
    "Une valeur existe déjà en base — cochez le champ dans « Paramètres paie extraits » pour l'écraser.",
  unknown: "Consultez le détail ou contactez le support si le problème persiste.",
};
