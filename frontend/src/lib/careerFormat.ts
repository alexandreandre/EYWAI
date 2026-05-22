export function formatDateFR(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = iso.includes("T") ? new Date(iso) : new Date(`${iso}T12:00:00`);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export function formatDateTimeFR(iso: string): string {
  try {
    return new Date(iso).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function formatEuroAmount(n: number): string {
  return `${n.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

export function formatCurrency(salary: { valeur: number; devise: string } | null): string {
  if (!salary?.valeur) return "—";
  return `${salary.valeur.toLocaleString("fr-FR")} ${salary.devise || "EUR"}`;
}
