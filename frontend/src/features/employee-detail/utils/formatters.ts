export function formatEuroAmount(n: number): string {
  return `${n.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

export function formatDateFR(iso: string): string {
  if (!iso) return "";
  const d = iso.includes("T") ? new Date(iso) : new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("fr-FR");
}

export function valeurSalaireBrut(obj: unknown): number {
  if (obj && typeof obj === "object" && obj !== null && "valeur" in obj) {
    const v = (obj as { valeur: unknown }).valeur;
    if (typeof v === "number" && !Number.isNaN(v)) return v;
    if (typeof v === "string") {
      const p = parseFloat(v.replace(",", "."));
      return Number.isNaN(p) ? 0 : p;
    }
  }
  return 0;
}
