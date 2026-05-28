export function formatMonthOverMonthDelta(pct: number | null): string | null {
  if (pct == null || Number.isNaN(pct)) return null;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)} % vs mois précédent`;
}
