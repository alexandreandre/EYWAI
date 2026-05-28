/** Libellés FR des actions journalisées (partagé Analytics + Administration EYWAI). */
export const ACTIONS_LABELS: Record<string, string> = {
  "employee.create": "Création salarié",
  "employee.update": "Modification salarié",
  "employee.delete": "Suppression salarié",
  "payslip.validate": "Validation bulletin",
  "payslip.generate": "Génération bulletin",
  "absence.validate": "Validation absence",
  "absence.reject": "Refus absence",
  "document.sign": "Signature document",
  "salary.update": "Modification salaire",
  "recruitment.hire": "Embauche candidat",
  "user.create": "Création utilisateur",
  "user.update": "Modification utilisateur",
  "user.role_change": "Changement de rôle",
  "company.create": "Création entreprise",
  "company.update": "Modification entreprise",
  "access.permission_change": "Modification des droits",
  "support.ticket_status_change": "Mise à jour ticket support",
  "collective_agreement.assign": "Attribution convention collective",
};

export function getActionLabel(action: string): string {
  return ACTIONS_LABELS[action] ?? action;
}
