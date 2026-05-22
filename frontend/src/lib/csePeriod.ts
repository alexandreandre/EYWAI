/** Bornes ISO (YYYY-MM-DD) du mois calendaire. */
export function getMonthPeriod(year: number, monthIndex: number): {
  periodStart: string;
  periodEnd: string;
  label: string;
} {
  const periodStart = new Date(year, monthIndex, 1).toISOString().split("T")[0];
  const periodEnd = new Date(year, monthIndex + 1, 0).toISOString().split("T")[0];
  const label = new Date(year, monthIndex, 1).toLocaleDateString("fr-FR", {
    month: "long",
    year: "numeric",
  });
  return { periodStart, periodEnd, label: label.charAt(0).toUpperCase() + label.slice(1) };
}

export function getCurrentMonthPeriod(): ReturnType<typeof getMonthPeriod> {
  const now = new Date();
  return getMonthPeriod(now.getFullYear(), now.getMonth());
}
