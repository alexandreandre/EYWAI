import type { CompanyKPIs, CompanyOverview } from "@/api/company";

const eur = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

type Stat = { label: string; value: string };

export function CompanyRhStatsBand({
  overview,
  kpis,
  periodExtras,
}: {
  overview: CompanyOverview;
  kpis: CompanyKPIs;
  periodExtras: {
    net: number;
    payrollTaxRate: number;
    avgCostPerEmployee: number;
  };
}): JSX.Element {
  const d = overview.demographics;
  const m = overview.movements;
  const stats: Stat[] = [
    { label: "ETP", value: d.total_etp.toLocaleString("fr-FR", { maximumFractionDigits: 1 }) },
    { label: "Ancienneté moy.", value: `${d.average_tenure_years} ans` },
    { label: "Âge moyen", value: d.average_age_years > 0 ? `${d.average_age_years} ans` : "—" },
    { label: "% cadres", value: `${d.cadre_percent} %` },
    {
      label: "H / F",
      value:
        d.male_percent != null && d.female_percent != null
          ? `${d.male_percent} % / ${d.female_percent} %`
          : "—",
    },
    { label: "Net versé", value: eur.format(periodExtras.net) },
    { label: "Taux charges", value: `${periodExtras.payrollTaxRate} %` },
    { label: "Coût moy. / sal.", value: eur.format(periodExtras.avgCostPerEmployee) },
    { label: "CDD < 30 j", value: String(overview.cdd_ending_within_30_days) },
    {
      label: "Absentéisme (30j)",
      value: `${overview.absenteeism.absenteeism_rate_percent} %`,
    },
    { label: "Embauches 30j", value: `+${m.new_hires_30_days}` },
    { label: "Embauches 90j", value: `+${m.new_hires_90_days}` },
    { label: "Embauches 12m", value: `+${m.new_hires_12_months}` },
    { label: "Turn-over 12m", value: `${m.turnover_rate_12_months} %` },
    { label: "Effectif", value: String(kpis.total_employees) },
  ];

  return (
    <div className="rounded-lg border bg-card overflow-x-auto">
      <div className="flex divide-x min-w-max">
        {stats.map((s) => (
          <div key={s.label} className="px-4 py-3 min-w-[7rem]">
            <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              {s.label}
            </p>
            <p className="text-sm font-semibold tabular-nums mt-0.5">{s.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
