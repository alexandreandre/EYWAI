import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import apiClient from '@/api/apiClient';
import { getTrend, type AlertLevel, type PayslipAlert, type TrendMonth } from '@/api/payslips';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { formatEuro, formatMonthYearFr } from '@/components/payslip/PayslipComparisonTab';

export interface PayslipTrendTabProps {
  payslipId: string;
  referenceYear: number;
  referenceMonth: number;
  /** Cible au clic sur une ligne du tableau (défaut : édition RH). Espace collaborateur : `/employee/payslips/:id`. */
  payslipRowHref?: (payslipId: string) => string;
}

type TimelinePoint = {
  key: string;
  label: string;
  year: number;
  month: number;
  salaire_brut: number | null;
  net_a_payer: number | null;
  total_cotisations: number | null;
  missing: boolean;
  payslip_id: string | null;
  alerts: PayslipAlert[];
};

function monthIndex(y: number, m: number): number {
  return y * 12 + m;
}

function prevCalendarMonth(y: number, m: number): { y: number; m: number } {
  if (m <= 1) return { y: y - 1, m: 12 };
  return { y, m: m - 1 };
}

function buildTimeline(
  months: TrendMonth[],
  refYear: number,
  refMonth: number
): TimelinePoint[] {
  if (!months.length) return [];
  const sorted = [...months].sort((a, b) => monthIndex(a.year, a.month) - monthIndex(b.year, b.month));
  const start = sorted[0];
  const end = prevCalendarMonth(refYear, refMonth);
  const map = new Map<string, TrendMonth>();
  sorted.forEach((row) => map.set(`${row.year}-${row.month}`, row));

  const out: TimelinePoint[] = [];
  let y = start.year;
  let m = start.month;
  const endIdx = monthIndex(end.y, end.m);
  while (monthIndex(y, m) <= endIdx) {
    const k = `${y}-${m}`;
    const row = map.get(k);
    out.push({
      key: k,
      label: formatMonthYearFr(m, y),
      year: y,
      month: m,
      salaire_brut: row?.salaire_brut ?? null,
      net_a_payer: row?.net_a_payer ?? null,
      total_cotisations: row?.total_cotisations ?? null,
      missing: !row,
      payslip_id: row?.payslip_id ?? null,
      alerts: row?.alerts ?? [],
    });
    m += 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
  }
  return out;
}

function maxActiveSeverity(alerts: PayslipAlert[]): AlertLevel | null {
  const active = alerts.filter((a) => a.status === 'active');
  if (active.some((a) => a.level === 'CRITIQUE')) return 'CRITIQUE';
  if (active.some((a) => a.level === 'AVERTISSEMENT')) return 'AVERTISSEMENT';
  if (active.some((a) => a.level === 'INFO')) return 'INFO';
  return null;
}

function pctDelta(cur: number | null, prev: number | null): number | null {
  if (cur === null || prev === null || prev === 0) return null;
  return ((cur - prev) / prev) * 100;
}

export function PayslipTrendTab({
  payslipId,
  referenceYear,
  referenceMonth,
  payslipRowHref,
}: PayslipTrendTabProps) {
  const navigate = useNavigate();
  const rowHref = payslipRowHref ?? ((id: string) => `/payslips/${id}/edit`);
  const [showBrut, setShowBrut] = useState(true);
  const [showNet, setShowNet] = useState(true);
  const [showCotis, setShowCotis] = useState(true);

  const trendQuery = useQuery({
    queryKey: ['payslip-trend', payslipId],
    queryFn: () => getTrend(payslipId),
  });

  const empQuery = useQuery({
    queryKey: ['employee', trendQuery.data?.employee_id],
    queryFn: async () => {
      const id = trendQuery.data!.employee_id;
      const r = await apiClient.get<{ first_name?: string; last_name?: string }>(
        `/api/employees/${id}`
      );
      return r.data;
    },
    enabled: !!trendQuery.data?.employee_id,
  });

  const timeline = useMemo(() => {
    if (!trendQuery.data?.months) return [];
    return buildTimeline(trendQuery.data.months, referenceYear, referenceMonth);
  }, [trendQuery.data, referenceYear, referenceMonth]);

  const chartData = useMemo(
    () =>
      timeline.map((p) => ({
        ...p,
        brut: p.missing ? null : p.salaire_brut,
        net: p.missing ? null : p.net_a_payer,
        cotis: p.missing ? null : p.total_cotisations,
      })),
    [timeline]
  );

  if (trendQuery.isLoading) {
    return (
      <div className="space-y-4 mt-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  if (trendQuery.isError) {
    return (
      <Card className="mt-6 border-destructive/60">
        <CardContent className="pt-6 text-sm text-destructive">
          Impossible de charger la tendance.
          <Button variant="outline" className="ml-4" onClick={() => trendQuery.refetch()}>
            Réessayer
          </Button>
        </CardContent>
      </Card>
    );
  }

  const empName = empQuery.data
    ? [empQuery.data.first_name, empQuery.data.last_name].filter(Boolean).join(' ') || '—'
    : empQuery.isError
      ? 'Salarié'
      : empQuery.isLoading
        ? '…'
        : '—';
  const periodLabel =
    timeline.length > 0
      ? `${timeline[0].label} → ${timeline[timeline.length - 1].label}`
      : '—';

  const CustomTooltip = ({
    active,
    payload,
  }: {
    active?: boolean;
    payload?: Array<{ payload: TimelinePoint & { brut?: number | null; net?: number | null; cotis?: number | null } }>;
  }) => {
    if (!active || !payload?.length) return null;
    const pl = payload[0].payload;
    return (
      <div className="rounded-md border bg-background/95 px-3 py-2 text-xs shadow-md">
        <p className="font-medium mb-1">{pl.label}</p>
        {pl.missing ? (
          <p className="text-muted-foreground">Bulletin absent</p>
        ) : (
          <>
            <p>Brut : {formatEuro(pl.salaire_brut)}</p>
            <p>Net : {formatEuro(pl.net_a_payer)}</p>
            <p>Cotisations : {formatEuro(pl.total_cotisations)}</p>
            {pl.alerts.length > 0 ? (
              <ul className="mt-2 list-disc pl-4 text-muted-foreground">
                {pl.alerts.map((a) => (
                  <li key={a.rule_id + a.message}>{a.message}</li>
                ))}
              </ul>
            ) : null}
          </>
        )}
      </div>
    );
  };

  const renderDot =
    () =>
    (props: {
      cx?: number;
      cy?: number;
      payload?: TimelinePoint & { brut?: number | null; net?: number | null; cotis?: number | null };
    }) => {
      const { cx = 0, cy = 0, payload } = props;
      if (!payload || payload.missing) {
        return <circle cx={cx} cy={cy} r={4} fill="#94a3b8" stroke="#fff" strokeWidth={1} />;
      }
      const sev = maxActiveSeverity(payload.alerts);
      if (sev === 'CRITIQUE')
        return <circle cx={cx} cy={cy} r={6} fill="#dc2626" stroke="#fff" strokeWidth={1} />;
      if (sev === 'AVERTISSEMENT')
        return <circle cx={cx} cy={cy} r={5} fill="#ea580c" stroke="#fff" strokeWidth={1} />;
      if (sev === 'INFO')
        return <circle cx={cx} cy={cy} r={4} fill="#0284c7" stroke="#fff" strokeWidth={1} />;
      return <circle cx={cx} cy={cy} r={3} fill="#64748b" stroke="#fff" strokeWidth={1} />;
    };

  return (
    <div className="space-y-6 mt-6">
      <div>
        <h2 className="text-xl font-semibold">Tendance</h2>
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{empName}</span>
          {' · '}
          Période couverte : {periodLabel}
        </p>
      </div>

      <div className="flex flex-wrap gap-6 items-center">
        <div className="flex items-center gap-2">
          <Checkbox id="trend-brut" checked={showBrut} onCheckedChange={(v) => setShowBrut(!!v)} />
          <Label htmlFor="trend-brut">Brut de base</Label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox id="trend-net" checked={showNet} onCheckedChange={(v) => setShowNet(!!v)} />
          <Label htmlFor="trend-net">Net à payer</Label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox id="trend-cotis" checked={showCotis} onCheckedChange={(v) => setShowCotis(!!v)} />
          <Label htmlFor="trend-cotis">Cotisations salariales</Label>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Évolution mensuelle</CardTitle>
          <p className="text-xs text-muted-foreground">
            Les segments grisés indiquent un mois sans bulletin validé dans la chaîne.
          </p>
        </CardHeader>
        <CardContent className="h-80 w-full min-h-[320px]">
          {chartData.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune donnée de tendance.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={56} />
                <YAxis
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) =>
                    Number(v).toLocaleString('fr-FR', { maximumFractionDigits: 0 })
                  }
                />
                <Tooltip
                  content={(props: { active?: boolean; payload?: Array<{ payload: TimelinePoint & { brut?: number | null; net?: number | null; cotis?: number | null } }> }) => (
                    <CustomTooltip active={props.active} payload={props.payload} />
                  )}
                />
                <Legend />
                {chartData.map((p) =>
                  p.missing ? (
                    <ReferenceArea
                      key={`miss-${p.key}`}
                      x1={p.label}
                      x2={p.label}
                      strokeOpacity={0}
                      fill="#e2e8f0"
                      fillOpacity={0.85}
                      label={{
                        value: 'Bulletin absent',
                        position: 'insideTop',
                        fill: '#64748b',
                        fontSize: 10,
                      }}
                    />
                  ) : null
                )}
                {showBrut ? (
                  <Line
                    type="monotone"
                    dataKey="brut"
                    name="Brut de base"
                    stroke="#2563eb"
                    strokeWidth={2}
                    connectNulls
                    dot={renderDot()}
                  />
                ) : null}
                {showNet ? (
                  <Line
                    type="monotone"
                    dataKey="net"
                    name="Net à payer"
                    stroke="#16a34a"
                    strokeWidth={2}
                    connectNulls
                    dot={renderDot()}
                  />
                ) : null}
                {showCotis ? (
                  <Line
                    type="monotone"
                    dataKey="cotis"
                    name="Cotisations salariales"
                    stroke="#ea580c"
                    strokeWidth={2}
                    connectNulls
                    dot={renderDot()}
                  />
                ) : null}
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Synthèse</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Mois</TableHead>
                <TableHead className="text-right">Brut</TableHead>
                <TableHead className="text-right">Net</TableHead>
                <TableHead className="text-right">Cotisations</TableHead>
                <TableHead className="text-right">Δ Brut %</TableHead>
                <TableHead className="text-right">Δ Net %</TableHead>
                <TableHead>Alertes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {timeline.map((row, i) => {
                const prev = i > 0 ? timeline[i - 1] : null;
                const dBrut = pctDelta(row.salaire_brut, prev?.salaire_brut ?? null);
                const dNet = pctDelta(row.net_a_payer, prev?.net_a_payer ?? null);
                const sev = maxActiveSeverity(row.alerts);
                const rowClass =
                  sev === 'CRITIQUE'
                    ? 'bg-red-50/80 dark:bg-red-950/25'
                    : sev === 'AVERTISSEMENT'
                      ? 'bg-orange-50/80 dark:bg-orange-950/20'
                      : sev === 'INFO'
                        ? 'bg-sky-50/70 dark:bg-sky-950/20'
                        : '';
                return (
                  <TableRow
                    key={row.key}
                    className={cn(
                      rowClass,
                      row.payslip_id ? 'cursor-pointer hover:bg-muted/50' : ''
                    )}
                    onClick={() => {
                      if (!row.payslip_id) return;
                      navigate(rowHref(row.payslip_id));
                    }}
                  >
                    <TableCell className="font-medium">{row.label}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {row.missing ? (
                        <span className="text-muted-foreground">Bulletin absent</span>
                      ) : (
                        formatEuro(row.salaire_brut)
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {row.missing ? '—' : formatEuro(row.net_a_payer)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {row.missing ? '—' : formatEuro(row.total_cotisations)}
                    </TableCell>
                    <TableCell
                      className={cn(
                        'text-right tabular-nums text-sm',
                        dBrut != null && dBrut < 0 && 'text-red-600',
                        dBrut != null && dBrut > 0 && 'text-emerald-600'
                      )}
                    >
                      {dBrut === null ? '—' : `${dBrut.toFixed(2)} %`}
                    </TableCell>
                    <TableCell
                      className={cn(
                        'text-right tabular-nums text-sm',
                        dNet != null && dNet < 0 && 'text-red-600',
                        dNet != null && dNet > 0 && 'text-emerald-600'
                      )}
                    >
                      {dNet === null ? '—' : `${dNet.toFixed(2)} %`}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-[220px]">
                      {row.alerts.length
                        ? row.alerts.map((a) => a.message).join(' · ')
                        : '—'}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
