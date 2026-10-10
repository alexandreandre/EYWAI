const STATUTS: Record<string, string> = {
  validated: "Validé",
  applied_payroll: "Appliqué à la paie",
  pending: "En attente",
  rejected: "Refusé",
};

/** Libellé français du statut d'un mouvement du compte d'heures. */
export function libelleStatutMouvement(status: string): string {
  if (!status) return "—";
  return STATUTS[status] ?? "Statut inconnu";
}
