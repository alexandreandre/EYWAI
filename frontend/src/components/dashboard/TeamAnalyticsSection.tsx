import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BarChart3, LayoutList, RefreshCw } from "lucide-react";

import {
  getTeamAnalytics,
  getTeams,
  type TeamAnalyticsItem,
} from "@/api/teams";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

const eur = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
});

function triggerDownload(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.setAttribute("download", filename);
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

function escapeCsvCell(v: string): string {
  if (/[;\n"]/.test(v)) {
    return `"${v.replace(/"/g, '""')}"`;
  }
  return v;
}

function formatPeriodRange(start: string, end: string): string {
  return `${start}_${end}`;
}

function boundsEqual(
  a: { start: string; end: string },
  b: { start: string; end: string },
): boolean {
  return a.start === b.start && a.end === b.end;
}

type SortColumn =
  | "team"
  | "effectif"
  | "masse"
  | "notes"
  | "absences"
  | "cout";
type SortDirection = "asc" | "desc";

type ChartMetric = "masse_brute" | "notes" | "cout_moyen";

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function currentMonthBounds(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return { start: toISODate(start), end: toISODate(end) };
}

function currentQuarterBounds(): { start: string; end: string } {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth();
  const q = Math.floor(m / 3);
  const startMonth = q * 3;
  const start = new Date(y, startMonth, 1);
  const end = new Date(y, startMonth + 3, 0);
  return { start: toISODate(start), end: toISODate(end) };
}

function currentYearBounds(): { start: string; end: string } {
  const y = new Date().getFullYear();
  return {
    start: toISODate(new Date(y, 0, 1)),
    end: toISODate(new Date(y, 11, 31)),
  };
}

function isSansEquipe(it: TeamAnalyticsItem): boolean {
  return it.team_id == null || it.team_id === "";
}

function partitionItems(items: TeamAnalyticsItem[]): {
  withTeam: TeamAnalyticsItem[];
  sans: TeamAnalyticsItem[];
} {
  const sans: TeamAnalyticsItem[] = [];
  const withTeam: TeamAnalyticsItem[] = [];
  for (const it of items) {
    if (isSansEquipe(it)) sans.push(it);
    else withTeam.push(it);
  }
  return { withTeam, sans };
}

function sortItems(
  items: TeamAnalyticsItem[],
  col: SortColumn,
  dir: SortDirection,
): TeamAnalyticsItem[] {
  const mul = dir === "asc" ? 1 : -1;
  const cmp = (a: TeamAnalyticsItem, b: TeamAnalyticsItem): number => {
    switch (col) {
      case "team":
        return (
          mul * a.team_name.localeCompare(b.team_name, "fr", { sensitivity: "base" })
        );
      case "effectif":
        return mul * (a.employee_count - b.employee_count);
      case "masse":
        return mul * (a.masse_salariale_brute - b.masse_salariale_brute);
      case "notes":
        return mul * (a.notes_de_frais - b.notes_de_frais);
      case "absences":
        return mul * (a.absences_jours - b.absences_jours);
      case "cout":
        return mul * (a.cout_moyen_par_salarie - b.cout_moyen_par_salarie);
      default:
        return 0;
    }
  };
  return [...items].sort(cmp);
}

export default function TeamAnalyticsSection() {
  const { toast } = useToast();
  const [period, setPeriod] = useState(() => currentMonthBounds());
  const isCurrentMonth = boundsEqual(period, currentMonthBounds());
  const [selectedTeamIds, setSelectedTeamIds] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<"table" | "chart">("table");
  const [chartMetric, setChartMetric] = useState<ChartMetric>("masse_brute");
  const [sortColumn, setSortColumn] = useState<SortColumn>("team");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const teamsQuery = useQuery({
    queryKey: ["teams-active"],
    queryFn: () => getTeams(false),
  });

  const analyticsQuery = useQuery({
    queryKey: [
      "team-analytics",
      period.start,
      period.end,
      [...selectedTeamIds].sort().join(","),
    ],
    queryFn: () =>
      getTeamAnalytics({
        period_start: period.start,
        period_end: period.end,
        team_ids: selectedTeamIds.length > 0 ? selectedTeamIds : undefined,
      }),
    enabled: Boolean(period.start && period.end),
  });

  const activeTeamsSorted = useMemo(
    () =>
      [...(teamsQuery.data?.teams ?? [])].sort((a, b) =>
        a.name.localeCompare(b.name, "fr", { sensitivity: "base" }),
      ),
    [teamsQuery.data?.teams],
  );

  const rawItems = analyticsQuery.data?.items ?? [];

  const displayRows = useMemo(() => {
    const { withTeam, sans } = partitionItems(rawItems);
    const sortedCore = sortItems(withTeam, sortColumn, sortDirection);
    const sortedSans = sortItems(sans, sortColumn, sortDirection);
    return [...sortedCore, ...sortedSans];
  }, [rawItems, sortColumn, sortDirection]);

  const toggleSort = (col: SortColumn) => {
    if (sortColumn === col) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(col);
      setSortDirection(col === "team" ? "asc" : "desc");
    }
  };

  const headerSortLabel = (col: SortColumn, label: string) => (
    <button
      type="button"
      className="inline-flex items-center gap-1 font-medium hover:text-foreground"
      onClick={() => toggleSort(col)}
    >
      {label}
      {sortColumn === col ? (
        <span className="text-xs text-muted-foreground">
          {sortDirection === "asc" ? "↑" : "↓"}
        </span>
      ) : null}
    </button>
  );

  const chartData = useMemo(() => {
    return displayRows.map((it) => {
      let value = 0;
      if (chartMetric === "masse_brute") value = it.masse_salariale_brute;
      else if (chartMetric === "notes") value = it.notes_de_frais;
      else value = it.cout_moyen_par_salarie;
      return {
        name: it.team_name.length > 18 ? `${it.team_name.slice(0, 16)}…` : it.team_name,
        fullName: it.team_name,
        value,
        team_color: it.team_color,
        raw: it,
      };
    });
  }, [displayRows, chartMetric]);

  const generateCSV = useCallback(
    (items: TeamAnalyticsItem[]) => {
      const headers = [
        "Équipe",
        "Effectif",
        "Masse brute",
        "Notes de frais",
        "Absences (jours)",
        "Taux absentéisme",
        "Coût moyen",
      ];
      const lines = [headers.join(";")];
      for (const it of items) {
        const row = [
          escapeCsvCell(it.team_name),
          String(it.employee_count),
          String(it.masse_salariale_brute).replace(".", ","),
          String(it.notes_de_frais).replace(".", ","),
          String(it.absences_jours).replace(".", ","),
          String(it.taux_absenteisme).replace(".", ","),
          String(it.cout_moyen_par_salarie).replace(".", ","),
        ];
        lines.push(row.join(";"));
      }
      const csv = "\uFEFF" + lines.join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      triggerDownload(
        blob,
        `analyse-equipes-${formatPeriodRange(period.start, period.end)}.csv`,
      );
    },
    [period.end, period.start],
  );

  const onRowOrBarDrill = useCallback(() => {
    toast({
      title: "Bientôt disponible",
      description: "Détail par salarié disponible en V2.",
    });
  }, [toast]);

  const toggleTeamFilter = (id: string, checked: boolean) => {
    setSelectedTeamIds((prev) => {
      if (checked) return [...prev, id];
      return prev.filter((x) => x !== id);
    });
  };

  const selectAllTeams = () => setSelectedTeamIds([]);
  const clearTeamSelection = () => setSelectedTeamIds([]);

  const totals = analyticsQuery.data;

  const noTeamsConfigured =
    !teamsQuery.isLoading &&
    (teamsQuery.data?.teams?.length ?? 0) === 0;

  return (
    <Card className="border-primary/10 shadow-sm">
      <CardHeader className="space-y-4 pb-2">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="text-lg">Analyse par équipe</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              Période {period.start} → {period.end}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant={isCurrentMonth ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriod(currentMonthBounds())}
            >
              Ce mois
            </Button>
            <Button
              type="button"
              variant={
                boundsEqual(period, currentQuarterBounds())
                  ? "default"
                  : "outline"
              }
              size="sm"
              onClick={() => setPeriod(currentQuarterBounds())}
            >
              Ce trimestre
            </Button>
            <Button
              type="button"
              variant={
                boundsEqual(period, currentYearBounds())
                  ? "default"
                  : "outline"
              }
              size="sm"
              onClick={() => setPeriod(currentYearBounds())}
            >
              Cette année
            </Button>
          </div>
        </div>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2 flex-1 min-w-0">
            <Label className="text-xs text-muted-foreground">
              Filtrer par équipe (vide = toutes)
            </Label>
            <div className="flex flex-wrap gap-3 rounded-md border bg-muted/20 p-3 max-h-36 overflow-y-auto">
              <div className="flex items-center gap-2 w-full sm:w-auto">
                <Checkbox
                  id="team-filter-all"
                  checked={selectedTeamIds.length === 0}
                  onCheckedChange={(c) => {
                    if (c === true) selectAllTeams();
                  }}
                />
                <label htmlFor="team-filter-all" className="text-sm cursor-pointer">
                  Toutes les équipes
                </label>
              </div>
              {activeTeamsSorted.map((t) => (
                <div key={t.id} className="flex items-center gap-2">
                  <Checkbox
                    id={`team-${t.id}`}
                    checked={selectedTeamIds.includes(t.id)}
                    onCheckedChange={(c) =>
                      toggleTeamFilter(t.id, c === true)
                    }
                  />
                  <label
                    htmlFor={`team-${t.id}`}
                    className="text-sm cursor-pointer inline-flex items-center gap-2"
                  >
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-border"
                      style={{ backgroundColor: t.color }}
                    />
                    {t.name}
                  </label>
                </div>
              ))}
              {selectedTeamIds.length > 0 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-8"
                  onClick={clearTeamSelection}
                >
                  Réinitialiser le filtre
                </Button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs text-muted-foreground">Vue</span>
            <ToggleGroup
              type="single"
              value={viewMode}
              onValueChange={(v) => {
                if (v === "table" || v === "chart") setViewMode(v);
              }}
            >
              <ToggleGroupItem value="table" aria-label="Tableau">
                <LayoutList className="h-4 w-4" />
              </ToggleGroupItem>
              <ToggleGroupItem value="chart" aria-label="Graphique">
                <BarChart3 className="h-4 w-4" />
              </ToggleGroupItem>
            </ToggleGroup>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {teamsQuery.isError && (
          <p className="text-sm text-destructive">
            Impossible de charger la liste des équipes.
          </p>
        )}

        {noTeamsConfigured && (
          <p className="text-sm text-muted-foreground text-center py-6">
            Créez vos premières équipes pour accéder aux vues analytiques.
          </p>
        )}

        {!noTeamsConfigured && analyticsQuery.isLoading && (
          <div className="space-y-2">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        )}

        {!noTeamsConfigured && analyticsQuery.isError && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-center space-y-2">
            <p className="text-sm text-destructive">
              Impossible de charger les indicateurs par équipe.
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => void analyticsQuery.refetch()}
            >
              <RefreshCw className="h-4 w-4" />
              Réessayer
            </Button>
          </div>
        )}

        {!noTeamsConfigured &&
          analyticsQuery.isSuccess &&
          viewMode === "table" && (
            <div className="rounded-md border overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="min-w-[140px]">
                      {headerSortLabel("team", "Équipe")}
                    </TableHead>
                    <TableHead className="text-right">
                      {headerSortLabel("effectif", "Effectif")}
                    </TableHead>
                    <TableHead className="text-right">
                      {headerSortLabel("masse", "Masse sal. brute")}
                    </TableHead>
                    <TableHead className="text-right">
                      {headerSortLabel("notes", "Notes de frais")}
                    </TableHead>
                    <TableHead className="text-right">
                      {headerSortLabel("absences", "Absences")}
                    </TableHead>
                    <TableHead className="text-right">
                      {headerSortLabel("cout", "Coût moyen / salarié")}
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {displayRows.map((it) => (
                    <TableRow
                      key={it.team_id ?? "sans-equipe"}
                      className={cn(
                        "cursor-pointer",
                        isSansEquipe(it) && "bg-muted/60",
                      )}
                      onClick={onRowOrBarDrill}
                    >
                      <TableCell>
                        <span className="inline-flex items-center gap-2">
                          <span
                            className="h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-border"
                            style={{ backgroundColor: it.team_color }}
                          />
                          {it.team_name}
                        </span>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {it.employee_count}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {eur.format(it.masse_salariale_brute)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {eur.format(it.notes_de_frais)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-sm">
                        {it.absences_jours.toFixed(1)}j ·{" "}
                        {it.taux_absenteisme.toFixed(1)}%
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {eur.format(it.cout_moyen_par_salarie)}
                      </TableCell>
                    </TableRow>
                  ))}
                  {totals && (
                    <TableRow className="bg-sky-50/90 hover:bg-sky-50/90 font-medium">
                      <TableCell>Total</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {totals.total_employees}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {eur.format(totals.total_masse_brute)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {eur.format(totals.total_notes_de_frais)}
                      </TableCell>
                      <TableCell className="text-right">—</TableCell>
                      <TableCell className="text-right">—</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          )}

        {!noTeamsConfigured &&
          analyticsQuery.isSuccess &&
          viewMode === "chart" && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Label className="text-xs shrink-0">Indicateur</Label>
                <Select
                  value={chartMetric}
                  onValueChange={(v) => {
                    if (
                      v === "masse_brute" ||
                      v === "notes" ||
                      v === "cout_moyen"
                    ) {
                      setChartMetric(v);
                    }
                  }}
                >
                  <SelectTrigger className="w-[min(100%,260px)]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="masse_brute">
                      Masse salariale brute
                    </SelectItem>
                    <SelectItem value="notes">Notes de frais</SelectItem>
                    <SelectItem value="cout_moyen">Coût moyen</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={chartData}
                  margin={{ top: 8, right: 8, left: 8, bottom: 48 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11 }}
                    interval={0}
                    angle={-35}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis
                    tickFormatter={(v) =>
                      eur.format(Number(v)).replace(/\u00a0/g, " ")
                    }
                    width={72}
                    tick={{ fontSize: 10 }}
                  />
                  <RechartsTooltip
                    formatter={(value: number | string) => [
                      eur.format(Number(value)),
                      "",
                    ]}
                    labelFormatter={(_, payload) => {
                      const p = payload?.[0]?.payload as
                        | { fullName?: string }
                        | undefined;
                      return p?.fullName ?? "";
                    }}
                  />
                  <Bar
                    dataKey="value"
                    radius={[4, 4, 0, 0]}
                    onClick={onRowOrBarDrill}
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`bar-${entry.name}-${index}`} fill={entry.team_color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

        {!noTeamsConfigured && analyticsQuery.isSuccess && (
          <div className="flex justify-end pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => generateCSV(displayRows)}
            >
              Exporter CSV
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
