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

const TAUX_PAR_TYPE: Record<string, string> = {
  travail_hs25: "25 %",
  travail_hs50: "50 %",
};

function heures(n: number): string {
  return `${n.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} h`;
}

/**
 * Ce qu'un mouvement du compteur contient, en clair (retour d'Elsa du 16/11 :
 * « à quoi correspond cet historique ? »). Un crédit dit les heures sup mises
 * au compteur par taux, le repos qu'elles donnent et ce qui a été payé.
 */
export function detailMouvement(m: {
  movement_type: string;
  hours: number;
  metadata?: Record<string, unknown> | null;
  note?: string | null;
}): string {
  const meta = (m.metadata ?? {}) as Record<string, unknown>;
  if (m.movement_type === "credit_hs") {
    const parType = (meta.heures_par_type ?? {}) as Record<string, number>;
    const morceaux = Object.entries(parType)
      .filter(([, h]) => Number(h) > 0)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([type, h]) => `${heures(Number(h))} sup à ${TAUX_PAR_TYPE[type] ?? type}`);
    const payees = Number(meta.hs_paid ?? 0);
    const debut = morceaux.length ? `${morceaux.join(", ")} → ` : "";
    const fin = payees > 0 ? ` ; ${heures(payees)} sup payées sur le bulletin` : "";
    return `${debut}${heures(m.hours)} de repos${fin}`;
  }
  if (m.movement_type === "debit_recovery") return "Repos pris, salaire maintenu";
  if (m.movement_type === "debit_payout") return "Solde payé sur le bulletin";
  return m.note ? String(m.note) : "—";
}
