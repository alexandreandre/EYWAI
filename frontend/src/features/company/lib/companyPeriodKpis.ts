import type { CompanyKPIs, MonthlyEvolution } from "@/api/company";
import type { PeriodSelection } from "@/lib/analyticsPeriod";

export type PeriodPayrollSnapshot = {
  gross: number;
  net: number;
  employerCharges: number;
  employeeCharges: number;
  totalCost: number;
  totalCharges: number;
  payrollTaxRate: number;
  previousGross: number;
  previousTotalCost: number;
};

function evolutionSeries(kpis: CompanyKPIs): MonthlyEvolution[] {
  return kpis.evolution_24_months?.length
    ? kpis.evolution_24_months
    : kpis.evolution_12_months ?? [];
}

function monthKey(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}`;
}

function findMonth(series: MonthlyEvolution[], key: string): MonthlyEvolution | undefined {
  return series.find((m) => m.month === key);
}

function sumYear(series: MonthlyEvolution[], year: number): MonthlyEvolution {
  const rows = series.filter((m) => m.month.startsWith(`${year}-`));
  return rows.reduce(
    (acc, row) => ({
      month: String(year),
      masse_salariale_brute: acc.masse_salariale_brute + row.masse_salariale_brute,
      net_verse: acc.net_verse + row.net_verse,
      charges_totales: acc.charges_totales + row.charges_totales,
      cout_total_employeur: acc.cout_total_employeur + row.cout_total_employeur,
    }),
    {
      month: String(year),
      masse_salariale_brute: 0,
      net_verse: 0,
      charges_totales: 0,
      cout_total_employeur: 0,
    },
  );
}

function snapshotFromRow(row: MonthlyEvolution): PeriodPayrollSnapshot {
  const gross = row.masse_salariale_brute;
  const charges = row.charges_totales;
  const payrollTaxRate = gross > 0 ? Math.round((charges / gross) * 10000) / 100 : 0;
  return {
    gross,
    net: row.net_verse,
    employerCharges: 0,
    employeeCharges: 0,
    totalCost: row.cout_total_employeur,
    totalCharges: charges,
    payrollTaxRate,
    previousGross: 0,
    previousTotalCost: 0,
  };
}

export function computePeriodPayroll(
  kpis: CompanyKPIs,
  period: PeriodSelection,
): PeriodPayrollSnapshot {
  const series = evolutionSeries(kpis);
  let current: MonthlyEvolution;
  let previous: MonthlyEvolution;

  if (period.granularity === "annual") {
    current = sumYear(series, period.year);
    previous = sumYear(series, period.year - 1);
  } else {
    const key = monthKey(period.year, period.month);
    current = findMonth(series, key) ?? {
      month: key,
      masse_salariale_brute: kpis.last_month_gross_salary,
      net_verse: kpis.last_month_net_salary,
      charges_totales: kpis.last_month_total_charges,
      cout_total_employeur: kpis.last_month_total_cost,
    };
    const prevKey = monthKey(period.year - 1, period.month);
    previous = findMonth(series, prevKey) ?? { month: prevKey, masse_salariale_brute: 0, net_verse: 0, charges_totales: 0, cout_total_employeur: 0 };
  }

  const snap = snapshotFromRow(current);
  snap.previousGross = previous.masse_salariale_brute;
  snap.previousTotalCost = previous.cout_total_employeur;
  if (period.granularity === "annual") {
    snap.previousGross = kpis.previous_year_gross_salary ?? previous.masse_salariale_brute;
    snap.previousTotalCost = kpis.previous_year_total_cost ?? previous.cout_total_employeur;
  }
  return snap;
}

export function percentDelta(current: number, previous: number): number | undefined {
  if (previous <= 0) return undefined;
  return Math.round(((current - previous) / previous) * 1000) / 10;
}

export function filterEvolutionForChart(
  kpis: CompanyKPIs,
  months: 6 | 12 | 24,
): MonthlyEvolution[] {
  const series = evolutionSeries(kpis);
  return series.slice(-months);
}
