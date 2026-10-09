/** Phrases des toasts de saisie en masse du calendrier, avec des pluriels accordés. */

export function pourEmployes(n: number): string {
  return `${n} ${n > 1 ? 'employés' : 'employé'}`;
}

export function messageBadgeuse(payload: {
  total_days_updated: number;
  employees_processed: number;
}): string {
  const employes = pourEmployes(payload.employees_processed);
  if (payload.total_days_updated === 0) {
    return `Aucun pointage de badgeuse n’existe pour cette période : rien n’a été importé pour ${employes}.`;
  }
  const jours = `${payload.total_days_updated} ${payload.total_days_updated > 1 ? 'jours' : 'jour'}`;
  return `${jours} mis à jour pour ${employes}.`;
}
