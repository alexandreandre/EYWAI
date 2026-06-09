import type { CompanyKPIs, CompanyOverview } from "@/api/company";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const eur = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

type Stat = { label: string; value: string };

function StatGrid({ stats }: { stats: Stat[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {stats.map((s) => (
        <div key={s.label} className="rounded-md border bg-muted/20 px-3 py-2">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            {s.label}
          </p>
          <p className="text-sm font-semibold tabular-nums mt-0.5">{s.value}</p>
        </div>
      ))}
    </div>
  );
}

export function CompanyRhStatsBand({
  overview,
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

  const effectifStats: Stat[] = [
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
    { label: "CDD < 30 j", value: String(overview.cdd_ending_within_30_days) },
  ];

  const paieStats: Stat[] = [
    { label: "Net versé", value: eur.format(periodExtras.net) },
    { label: "Coût moy. / sal.", value: eur.format(periodExtras.avgCostPerEmployee) },
  ];

  const mouvementsStats: Stat[] = [
    { label: "Embauches 90j", value: `+${m.new_hires_90_days}` },
    { label: "Embauches 12m", value: `+${m.new_hires_12_months}` },
    { label: "Turn-over 12m", value: `${m.turnover_rate_12_months} %` },
    {
      label: "Absentéisme (30j)",
      value: `${overview.absenteeism.absenteeism_rate_percent} %`,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Effectif & démographie</CardTitle>
        </CardHeader>
        <CardContent>
          <StatGrid stats={effectifStats} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Paie (période)</CardTitle>
        </CardHeader>
        <CardContent>
          <StatGrid stats={paieStats} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Mouvements & absentéisme</CardTitle>
        </CardHeader>
        <CardContent>
          <StatGrid stats={mouvementsStats} />
        </CardContent>
      </Card>
    </div>
  );
}
