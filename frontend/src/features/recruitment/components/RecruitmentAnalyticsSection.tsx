import { useState, useMemo, useCallback, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getRecruitmentAnalytics,
  type Job,
  type RecruitmentAnalyticsParams,
} from "@/api/recruitment";
import { eurFmt } from "./recruitmentUtils";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";

export function RecruitmentAnalyticsSection({
  companyId,
  jobs,
  initialJobId,
}: {
  companyId: string;
  jobs: Job[];
  initialJobId?: string | null;
}) {
  const [formJobId, setFormJobId] = useState("__all__");
  const [formDateFrom, setFormDateFrom] = useState("");
  const [formDateTo, setFormDateTo] = useState("");
  const [formBudget, setFormBudget] = useState("");
  const [queryParams, setQueryParams] = useState<RecruitmentAnalyticsParams>({});

  useEffect(() => {
    setFormJobId("__all__");
    setFormDateFrom("");
    setFormDateTo("");
    setFormBudget("");
    setQueryParams({});
  }, [companyId]);

  useEffect(() => {
    if (!initialJobId) return;
    setFormJobId(initialJobId);
    setQueryParams({ job_id: initialJobId });
  }, [initialJobId]);

  const commitFilters = useCallback(() => {
    const p: RecruitmentAnalyticsParams = {};
    if (formJobId && formJobId !== "__all__") p.job_id = formJobId;
    if (formDateFrom.trim()) p.date_from = formDateFrom.trim();
    if (formDateTo.trim()) p.date_to = formDateTo.trim();
    const raw = formBudget.trim().replace(/\s/g, "").replace(",", ".");
    if (raw) {
      const n = parseFloat(raw);
      if (!Number.isNaN(n)) p.budget_total = n;
    }
    setQueryParams(p);
  }, [formJobId, formDateFrom, formDateTo, formBudget]);

  const { data: analyticsData, isLoading, isFetching } = useQuery({
    queryKey: ["recruitment", "analytics", companyId, queryParams],
    queryFn: () => getRecruitmentAnalytics(companyId, queryParams),
    enabled: Boolean(companyId),
  });

  const loading = isLoading || isFetching;
  const d = analyticsData;
  const showCostCard = d != null && d.cost_per_hire != null;

  const sourceChartData = useMemo(
    () =>
      (d?.source_stats ?? []).map((s) => ({
        source: s.source.length > 28 ? `${s.source.slice(0, 28)}…` : s.source,
        fullSource: s.source,
        candidats: s.nb_candidates,
        embauches: s.nb_hired,
      })),
    [d?.source_stats],
  );

  const stageChartData = useMemo(
    () =>
      (d?.stage_conversion ?? []).map((s) => ({
        name: s.stage_name.length > 36 ? `${s.stage_name.slice(0, 36)}…` : s.stage_name,
        fullName: s.stage_name,
        candidats: s.nb_candidates,
        conversion: Math.round(s.conversion_rate * 10) / 10,
      })),
    [d?.stage_conversion],
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Filtres</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-end">
          <div className="min-w-0 space-y-2">
            <Label>Poste</Label>
            <Select value={formJobId} onValueChange={setFormJobId}>
              <SelectTrigger className="w-[260px]">
                <SelectValue placeholder="Poste" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Tous les postes</SelectItem>
                {jobs.map((j) => (
                  <SelectItem key={j.id} value={j.id}>
                    {j.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="an-date-from">Du</Label>
            <Input
              id="an-date-from"
              type="date"
              className="w-[180px]"
              value={formDateFrom}
              onChange={(e) => setFormDateFrom(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="an-date-to">Au</Label>
            <Input
              id="an-date-to"
              type="date"
              className="w-[180px]"
              value={formDateTo}
              onChange={(e) => setFormDateTo(e.target.value)}
            />
          </div>
          <div className="min-w-0 max-w-xs flex-1 space-y-2">
            <Label htmlFor="an-budget">Budget recrutement (€)</Label>
            <Input
              id="an-budget"
              inputMode="decimal"
              placeholder="Optionnel"
              value={formBudget}
              onChange={(e) => setFormBudget(e.target.value)}
            />
          </div>
          <Button type="button" onClick={commitFilters} disabled={!companyId} className="lg:mb-0.5">
            <RefreshCw className="h-4 w-4 mr-2" />
            Actualiser
          </Button>
        </CardContent>
      </Card>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      ) : (
        <>
          <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-2", showCostCard ? "lg:grid-cols-5" : "lg:grid-cols-4")}>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm font-medium text-muted-foreground">Total candidatures</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold tabular-nums">{d?.total_candidates ?? 0}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm font-medium text-muted-foreground">Total embauches</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold tabular-nums">{d?.total_hired ?? 0}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm font-medium text-muted-foreground">Taux de conversion global</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold tabular-nums">
                  {(d?.overall_conversion_rate ?? 0).toFixed(1)}%
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm font-medium text-muted-foreground">Temps moyen d&apos;embauche</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold tabular-nums">
                  {(d?.avg_time_to_hire_days ?? 0).toFixed(1)}
                  <span className="text-base font-normal text-muted-foreground ml-1">j</span>
                </p>
              </CardContent>
            </Card>
            {showCostCard && d?.cost_per_hire != null ? (
              <Card>
                <CardHeader className="pb-1">
                  <CardTitle className="text-sm font-medium text-muted-foreground">Coût par embauche</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold tabular-nums">{eurFmt.format(d.cost_per_hire)}</p>
                </CardContent>
              </Card>
            ) : null}
          </div>

          <div className="grid grid-cols-1 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Efficacité des sources</CardTitle>
                <p className="text-sm text-muted-foreground">Candidatures vs embauches par canal</p>
              </CardHeader>
              <CardContent>
                {!sourceChartData.length ? (
                  <p className="text-sm text-muted-foreground py-8 text-center">Aucune donnée</p>
                ) : (
                  <ResponsiveContainer width="100%" height={Math.max(220, sourceChartData.length * 40)}>
                    <BarChart
                      layout="vertical"
                      data={sourceChartData}
                      margin={{ top: 8, right: 24, left: 8, bottom: 8 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis type="number" allowDecimals={false} className="text-xs" />
                      <YAxis dataKey="source" type="category" width={100} tick={{ fontSize: 11 }} />
                      <RechartsTooltip
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null;
                          const p = payload[0].payload as {
                            fullSource?: string;
                            candidats?: number;
                            embauches?: number;
                          };
                          return (
                            <div className="rounded-md border bg-background px-2 py-1.5 text-xs shadow-md">
                              <p className="font-medium mb-1">{p.fullSource}</p>
                              <p className="text-muted-foreground">Candidats : {p.candidats}</p>
                              <p className="text-muted-foreground">Embauches : {p.embauches}</p>
                            </div>
                          );
                        }}
                      />
                      <Legend />
                      <Bar dataKey="candidats" name="Candidats" fill="#94a3b8" radius={[0, 4, 4, 0]} />
                      <Bar dataKey="embauches" name="Embauches" fill="#22c55e" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Conversion par étape</CardTitle>
                <p className="text-sm text-muted-foreground">Candidats par étape et taux vers l&apos;étape suivante</p>
              </CardHeader>
              <CardContent>
                {!stageChartData.length ? (
                  <p className="text-sm text-muted-foreground py-8 text-center">Aucune donnée</p>
                ) : (
                  <ResponsiveContainer width="100%" height={Math.min(520, 120 + stageChartData.length * 48)}>
                    <BarChart data={stageChartData} margin={{ top: 8, right: 16, left: 8, bottom: 80 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-35} textAnchor="end" height={90} />
                      <YAxis allowDecimals={false} className="text-xs" />
                      <RechartsTooltip
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null;
                          const p = payload[0].payload as {
                            fullName?: string;
                            candidats?: number;
                            conversion?: number;
                          };
                          return (
                            <div className="rounded-md border bg-background px-2 py-1.5 text-xs shadow-md">
                              <p className="font-medium mb-1">{p.fullName}</p>
                              <p className="text-muted-foreground">Candidats : {p.candidats}</p>
                              <p className="text-muted-foreground">
                                Conversion vers l&apos;étape suivante : {p.conversion ?? 0}%
                              </p>
                            </div>
                          );
                        }}
                      />
                      <Legend />
                      <Bar dataKey="candidats" name="Candidats" fill="#3b82f6" radius={[4, 4, 0, 0]}>
                        <LabelList
                          dataKey="conversion"
                          position="top"
                          formatter={(v: number) => (v > 0 ? `${v}%` : "")}
                          className="fill-muted-foreground text-[10px]"
                        />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
                {stageChartData.length > 0 && d?.stage_conversion?.length ? (
                  <ul className="mt-4 space-y-1 text-xs text-muted-foreground border-t pt-3">
                    {d.stage_conversion.map((s) => (
                      <li key={`${s.stage_name}-${s.stage_position}`} className="flex justify-between gap-2">
                        <span className="truncate" title={s.stage_name}>{s.stage_name}</span>
                        <span className="tabular-nums shrink-0">
                          {s.conversion_rate.toFixed(1)}% vers suivante · ~{s.avg_days_in_stage.toFixed(1)} j dans l&apos;étape
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Time-to-hire par poste</CardTitle>
              <p className="text-sm text-muted-foreground">Délai moyen entre candidature et embauche</p>
            </CardHeader>
            <CardContent>
              {!d?.time_to_hire_by_job?.length ? (
                <p className="text-sm text-muted-foreground py-8 text-center">Aucune embauche sur la période sélectionnée</p>
              ) : (
                <div className="w-full overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Poste</TableHead>
                        <TableHead className="text-right">Embauches</TableHead>
                        <TableHead className="text-right">Moy. jours</TableHead>
                        <TableHead className="text-right">Min</TableHead>
                        <TableHead className="text-right">Max</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {d.time_to_hire_by_job.map((row) => (
                        <TableRow key={row.job_id}>
                          <TableCell className="font-medium">{row.job_title || "—"}</TableCell>
                          <TableCell className="text-right tabular-nums">{row.nb_hired}</TableCell>
                          <TableCell className="text-right tabular-nums">{row.avg_days.toFixed(1)}</TableCell>
                          <TableCell className="text-right tabular-nums">{row.min_days.toFixed(1)}</TableCell>
                          <TableCell className="text-right tabular-nums">{row.max_days.toFixed(1)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
