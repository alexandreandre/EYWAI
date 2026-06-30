/**
 * Vue consolidée groupe : masse salariale, effectifs, KPIs inter-entreprises.
 */

import { pageTitleClassName } from '@/components/layout';
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import {
  Users,
  Building2,
  TrendingUp,
  ArrowLeft,
  Download,
  PieChart as PieChartIcon,
  Filter,
  ArrowUpDown,
  Percent,
  Calculator,
  Calendar,
  CheckCircle2,
  RefreshCw,
  Link2,
  MoreVertical,
  Settings,
} from "lucide-react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
  LineChart,
  Line,
} from "recharts";
import { toast } from "sonner";

import {
  fetchConsolidatedStats,
  fetchGroupDetails,
  fetchPayrollEvolution,
  type CompanyStats,
  type CompareToMode,
  type ConsolidatedStats,
  type EvolutionDataPoint,
  type GroupDetails,
} from "@/api/companyGroups";
import { KpiCard } from "@/components/analytics/KpiCard";
import { PayrollSourceBadge } from "@/components/analytics/PayrollSourceBadge";
import { SectionSkeleton } from "@/components/analytics/SectionSkeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/contexts/AuthContext";
import { isPlatformAdmin } from "@/lib/platformAdmin";
import { useCompany } from "@/contexts/CompanyContext";
import {
  chargeRateColorClass,
  computeCompanyKpis,
  computeDistribution,
  groupChargeRate,
  percentDelta,
  totalsEmployerCost,
} from "@/lib/groupConsolidatedKpis";
import { exportGroupDashboardXlsx, exportGroupDashboardTableXlsx } from "@/lib/exportGroupDashboardXlsx";
import {
  applyPreset,
  buildYearOptions,
  formatMonthLabel,
  getPeriodBounds,
  parsePeriodFromSearchParams,
  periodToSearchParams,
  type PeriodPreset,
  type PeriodState,
} from "@/lib/groupConsolidatedPeriod";

type SortKey = keyof CompanyStats;
type SortOrder = "asc" | "desc";

const COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
  "#3b82f6",
  "#10b981",
  "#6b7280",
];

const PRESET_LABELS: Record<PeriodPreset, string> = {
  current_month: "Mois courant",
  previous_month: "Mois précédent",
  ytd: "Année courante (YTD)",
  last_12_months: "12 derniers mois",
  previous_year: "Année N-1",
  custom: "Personnaliser",
};

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatCompactNumber(num: number): string {
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M€`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(0)}k€`;
  return formatCurrency(num);
}

function companyGrossFromComparison(
  comparison: ConsolidatedStats["comparison"],
  companyId: string,
): number | undefined {
  const row = comparison?.by_company?.find((c) => c.company_id === companyId);
  return row?.gross_salary;
}

export function GroupDashboard() {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const { setActiveCompany } = useCompany();

  const initial = parsePeriodFromSearchParams(searchParams);

  const [groupDetails, setGroupDetails] = useState<GroupDetails | null>(null);
  const [stats, setStats] = useState<ConsolidatedStats | null>(null);
  const [evolutionData, setEvolutionData] = useState<EvolutionDataPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [period, setPeriod] = useState<PeriodState>(initial.period);
  const [compareTo, setCompareTo] = useState<CompareToMode>(initial.compareTo);
  const [searchTerm, setSearchTerm] = useState(initial.searchTerm);
  const [sortKey, setSortKey] = useState<SortKey>("company_name");
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc");
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<Set<string>>(
    () => new Set(initial.selectedCompanyIds ?? []),
  );
  const [availableCompanies, setAvailableCompanies] = useState<CompanyStats[]>([]);
  const [evolutionView, setEvolutionView] = useState<"aggregate" | "by_company">("aggregate");
  const [evolutionMetric, setEvolutionMetric] = useState<
    "gross" | "charges" | "total" | "employees"
  >("gross");
  const [distributionBase, setDistributionBase] = useState<"employees" | "gross" | "cost">(
    "employees",
  );
  const [isExporting, setIsExporting] = useState(false);
  const [isExportingTable, setIsExportingTable] = useState(false);

  const periodBounds = useMemo(() => getPeriodBounds(period), [period]);
  const isPlatformAdminUser = isPlatformAdmin(user);

  const syncUrl = useCallback(
    (nextPeriod: PeriodState, nextCompare: CompareToMode, ids: Set<string>, q: string) => {
      const params = periodToSearchParams(nextPeriod, nextCompare, ids, q);
      setSearchParams(params, { replace: true });
    },
    [setSearchParams],
  );

  const loadGroupMeta = useCallback(async () => {
    if (!groupId) return;
    try {
      const details = await fetchGroupDetails(groupId);
      setGroupDetails(details);
    } catch {
      /* nom optionnel si accès limité */
    }
  }, [groupId]);

  const loadStats = useCallback(async () => {
    if (!groupId) {
      setError("ID de groupe manquant");
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      const { startYear, startMonth, endYear, endMonth } = periodBounds;
      const params =
        period.mode === "month"
          ? {
              year: endYear,
              month: endMonth,
              compare_to: compareTo !== "off" ? compareTo : undefined,
            }
          : {
              start_year: startYear,
              start_month: startMonth,
              end_year: endYear,
              end_month: endMonth,
              compare_to: compareTo !== "off" ? compareTo : undefined,
            };

      const [statsRes, evolutionRes] = await Promise.all([
        fetchConsolidatedStats(groupId, params),
        fetchPayrollEvolution(groupId, startYear, startMonth, endYear, endMonth),
      ]);

      setStats(statsRes);
      setEvolutionData(evolutionRes);

      if (statsRes.by_company?.length) {
        setAvailableCompanies(statsRes.by_company);
        setSelectedCompanyIds((prev) => {
          if (prev.size > 0) return prev;
          return new Set(statsRes.by_company.map((c) => c.company_id));
        });
      }
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(detail ?? "Erreur lors du chargement des statistiques");
    } finally {
      setIsLoading(false);
    }
  }, [groupId, periodBounds, compareTo, period.mode]);

  useEffect(() => {
    loadGroupMeta();
  }, [loadGroupMeta]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    syncUrl(period, compareTo, selectedCompanyIds, searchTerm);
  }, [period, compareTo, selectedCompanyIds, searchTerm, syncUrl]);

  const applyPeriodPreset = (preset: PeriodPreset) => {
    setPeriod(applyPreset(preset));
  };

  const filteredAndSortedCompanies = useMemo(() => {
    if (!stats?.by_company) return [];

    const filtered = stats.by_company.filter(
      (company) =>
        selectedCompanyIds.has(company.company_id) &&
        (company.company_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          company.siret?.includes(searchTerm)),
    );

    filtered.sort((a, b) => {
      const aValue = a[sortKey];
      const bValue = b[sortKey];
      if (typeof aValue === "string" && typeof bValue === "string") {
        return sortOrder === "asc"
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      }
      const aNum = Number(aValue) || 0;
      const bNum = Number(bValue) || 0;
      return sortOrder === "asc" ? aNum - bNum : bNum - aNum;
    });

    return filtered;
  }, [stats, searchTerm, sortKey, sortOrder, selectedCompanyIds]);

  const filteredTotals = useMemo(() => {
    if (!filteredAndSortedCompanies.length) {
      return {
        total_employees: 0,
        total_employees_excluding_rh: 0,
        total_active_employees_excluding_rh: 0,
        total_rh: 0,
        total_payslip_count: 0,
        total_gross_salary: 0,
        total_net_salary: 0,
        total_employer_charges: 0,
        average_gross_per_company: 0,
        average_employees_per_company: 0,
        company_count: 0,
      };
    }

    const totals = filteredAndSortedCompanies.reduce(
      (acc, company) => {
        acc.total_employees += company.total_employee_count;
        acc.total_employees_excluding_rh += company.employee_count;
        acc.total_active_employees_excluding_rh +=
          company.active_employee_count ?? company.employee_count;
        acc.total_rh += company.rh_count;
        acc.total_payslip_count += company.payslip_count;
        acc.total_gross_salary += company.gross_salary;
        acc.total_net_salary += company.net_salary;
        acc.total_employer_charges += company.employer_charges;
        return acc;
      },
      {
        total_employees: 0,
        total_employees_excluding_rh: 0,
        total_active_employees_excluding_rh: 0,
        total_rh: 0,
        total_payslip_count: 0,
        total_gross_salary: 0,
        total_net_salary: 0,
        total_employer_charges: 0,
        average_gross_per_company: 0,
        average_employees_per_company: 0,
        company_count: filteredAndSortedCompanies.length,
      },
    );

    totals.average_gross_per_company =
      totals.company_count > 0 ? totals.total_gross_salary / totals.company_count : 0;
    totals.average_employees_per_company =
      totals.company_count > 0 ? totals.total_employees / totals.company_count : 0;

    return totals;
  }, [filteredAndSortedCompanies]);

  const comparisonTotals = useMemo(() => {
    if (!stats?.comparison?.totals || !compareTo || compareTo === "off") return null;
    const compCompanies =
      stats.comparison.by_company?.filter((c) => selectedCompanyIds.has(c.company_id)) ?? [];
    if (compCompanies.length === 0) return stats.comparison.totals;

    return compCompanies.reduce(
      (acc, c) => {
        acc.total_employees += c.total_employee_count;
        acc.total_gross_salary += c.gross_salary;
        acc.total_employer_charges += c.employer_charges;
        return acc;
      },
      {
        total_employees: 0,
        total_gross_salary: 0,
        total_employer_charges: 0,
      },
    );
  }, [stats?.comparison, compareTo, selectedCompanyIds]);

  const chargeRate = groupChargeRate(filteredTotals);
  const avgGrossPerEmployee =
    filteredTotals.total_employees > 0
      ? filteredTotals.total_gross_salary / filteredTotals.total_employees
      : 0;
  const totalEmployerCostValue = totalsEmployerCost(filteredTotals);
  const effectivePeriodLabel = useMemo(() => {
    const fallbackYear = stats?.metadata.payroll_period_year;
    const fallbackMonth = stats?.metadata.payroll_period_month;
    if (stats?.metadata.payroll_fallback_applied && fallbackYear && fallbackMonth) {
      return `${formatMonthLabel(fallbackMonth)} ${fallbackYear}`;
    }
    return periodBounds.label;
  }, [periodBounds.label, stats?.metadata]);
  const requestedPeriodLabel = useMemo(() => {
    const requestedYear = stats?.metadata.requested_year;
    const requestedMonth = stats?.metadata.requested_month;
    if (stats?.metadata.payroll_fallback_applied && requestedYear && requestedMonth) {
      return `${formatMonthLabel(requestedMonth)} ${requestedYear}`;
    }
    return periodBounds.label;
  }, [periodBounds.label, stats?.metadata]);
  const effectivePeriodExportKey = useMemo(() => {
    const fallbackYear = stats?.metadata.payroll_period_year;
    const fallbackMonth = stats?.metadata.payroll_period_month;
    if (stats?.metadata.payroll_fallback_applied && fallbackYear && fallbackMonth) {
      return `${fallbackYear}-${String(fallbackMonth).padStart(2, "0")}`;
    }
    if (
      periodBounds.startYear === periodBounds.endYear &&
      periodBounds.startMonth === periodBounds.endMonth
    ) {
      return `${periodBounds.endYear}-${String(periodBounds.endMonth).padStart(2, "0")}`;
    }
    return `${periodBounds.startYear}${String(periodBounds.startMonth).padStart(2, "0")}-${periodBounds.endYear}${String(periodBounds.endMonth).padStart(2, "0")}`;
  }, [periodBounds, stats?.metadata]);

  const kpiDeltas = useMemo(() => {
    if (!comparisonTotals) return null;
    const prevCost =
      comparisonTotals.total_gross_salary + comparisonTotals.total_employer_charges;
    return {
      employees: percentDelta(
        filteredTotals.total_employees,
        comparisonTotals.total_employees,
      ),
      employerCost: percentDelta(totalEmployerCostValue, prevCost),
      gross: percentDelta(
        filteredTotals.total_gross_salary,
        comparisonTotals.total_gross_salary,
      ),
      charges: percentDelta(
        filteredTotals.total_employer_charges,
        comparisonTotals.total_employer_charges,
      ),
    };
  }, [comparisonTotals, filteredTotals, totalEmployerCostValue]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortOrder("asc");
    }
  };

  const handleCompanyRowClick = (companyId: string) => {
    setActiveCompany(companyId);
    navigate("/dashboard");
  };

  const copyShareLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      toast.success("Lien copié dans le presse-papiers");
    } catch {
      toast.error("Impossible de copier le lien");
    }
  };

  const chartData = useMemo(
    () =>
      filteredAndSortedCompanies.map((company) => ({
        name:
          company.company_name.length > 15
            ? `${company.company_name.substring(0, 15)}…`
            : company.company_name,
        fullName: company.company_name,
        employees: company.employee_count,
        rh: company.rh_count,
        grossSalary: company.gross_salary,
        charges: company.employer_charges,
      })),
    [filteredAndSortedCompanies],
  );

  const pieChartData = useMemo(() => {
    return filteredAndSortedCompanies.map((company) => {
      let value = company.total_employee_count;
      if (distributionBase === "gross") value = company.gross_salary;
      if (distributionBase === "cost")
        value = company.gross_salary + company.employer_charges;
      return { name: company.company_name, value };
    });
  }, [filteredAndSortedCompanies, distributionBase]);

  const evolutionChartData = useMemo(() => {
    const filteredEvolution = evolutionData.filter(
      (point) => selectedCompanyIds.size === 0 || selectedCompanyIds.has(point.company_id),
    );

    if (evolutionView === "by_company") {
      const byMonthCompany = new Map<string, Record<string, number>>();
      const companyNames = new Map<string, string>();

      filteredEvolution.forEach((point) => {
        const key = `${point.year}-${String(point.month).padStart(2, "0")}`;
        const monthLabel = `${formatMonthLabel(point.month).substring(0, 3)} ${point.year}`;
        companyNames.set(point.company_id, point.company_name);
        const row = byMonthCompany.get(key) ?? { month: monthLabel };
        row.month = monthLabel;
        let val = point.total_gross;
        if (evolutionMetric === "charges") val = point.total_employer_charges;
        if (evolutionMetric === "total")
          val = point.total_gross + point.total_employer_charges;
        if (evolutionMetric === "employees") val = point.employee_count;
        row[point.company_id] = (row[point.company_id] as number | undefined ?? 0) + val;
        byMonthCompany.set(key, row);
      });

      return {
        data: Array.from(byMonthCompany.values()) as Array<Record<string, string | number>>,
        series: Array.from(companyNames.entries()).map(([id, name]) => ({ id, name })),
      };
    }

    const byMonth = new Map<string, { month: string; gross: number; charges: number }>();
    filteredEvolution.forEach((point) => {
      const key = `${point.year}-${String(point.month).padStart(2, "0")}`;
      const monthLabel = `${formatMonthLabel(point.month).substring(0, 3)} ${point.year}`;
      const existing = byMonth.get(key);
      if (existing) {
        existing.gross += point.total_gross;
        existing.charges += point.total_employer_charges;
      } else {
        byMonth.set(key, {
          month: monthLabel,
          gross: point.total_gross,
          charges: point.total_employer_charges,
        });
      }
    });

    return {
      data: Array.from(byMonth.values()),
      series: [] as { id: string; name: string }[],
    };
  }, [evolutionData, selectedCompanyIds, evolutionView, evolutionMetric]);

  const kpiRows = useMemo(
    () => filteredAndSortedCompanies.map((c) => computeCompanyKpis(c)),
    [filteredAndSortedCompanies],
  );

  const chargeRates = kpiRows
    .filter((k) => k.chargeRate > 0)
    .map((k) => k.chargeRate);
  const costsPerEmployee = kpiRows
    .filter((k) => k.totalCostPerEmployee > 0)
    .map((k) => k.totalCostPerEmployee);
  const rhRatios = kpiRows.filter((k) => k.rhRatio > 0).map((k) => k.rhRatio);
  const salariesPerEmployee = kpiRows
    .filter((k) => k.grossPerEmployee > 0)
    .map((k) => k.grossPerEmployee);

  const distCharge = computeDistribution(chargeRates);
  const distCost = computeDistribution(costsPerEmployee);
  const distRh = computeDistribution(rhRatios);
  const distSalary = computeDistribution(salariesPerEmployee);

  const handleExportExcel = async () => {
    if (!stats) return;
    setIsExporting(true);
    try {
      await exportGroupDashboardXlsx({
        groupName: groupDetails?.group_name ?? "Groupe",
        siren: groupDetails?.siren,
        periodLabel: effectivePeriodLabel,
        periodExportKey: effectivePeriodExportKey,
        compareTo,
        companies: filteredAndSortedCompanies,
        totals: filteredTotals,
        chargeRate,
        avgGrossPerEmployee,
        totalEmployerCostValue,
        kpiRows,
        kpiDeltas,
        comparison: stats.comparison,
        distributions: {
          charge: distCharge,
          cost: distCost,
          rh: distRh,
          salary: distSalary,
        },
        evolution: evolutionData.filter(
          (point) =>
            selectedCompanyIds.size === 0 || selectedCompanyIds.has(point.company_id),
        ),
        generatedAt: stats.metadata.generated_at,
      });
      toast.success("Export Excel téléchargé");
    } catch {
      toast.error("Impossible de générer l'export Excel");
    } finally {
      setIsExporting(false);
    }
  };

  const handleExportTableExcel = async () => {
    if (!stats) return;
    setIsExportingTable(true);
    try {
      await exportGroupDashboardTableXlsx({
        groupName: groupDetails?.group_name ?? "Groupe",
        periodLabel: effectivePeriodLabel,
        periodExportKey: effectivePeriodExportKey,
        compareTo,
        companies: filteredAndSortedCompanies,
        totals: filteredTotals,
        totalEmployerCostValue,
        chargeRate,
        comparison: stats.comparison,
      });
      toast.success("Export Excel du tableau téléchargé");
    } catch {
      toast.error("Impossible de générer l'export Excel du tableau");
    } finally {
      setIsExportingTable(false);
    }
  };

  const handleBack = () => {
    if (isPlatformAdminUser && groupId) {
      navigate(`/super-admin/groups/${groupId}`);
    } else {
      navigate("/dashboard");
    }
  };

  const yearOptions = buildYearOptions(10);
  const noCompaniesSelected = selectedCompanyIds.size === 0 && availableCompanies.length > 0;

  if (error && !stats) {
    return (
      <div className="container mx-auto">
        <Button variant="ghost" size="sm" onClick={handleBack} className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Retour
        </Button>
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  const groupTitle = groupDetails?.group_name ?? "Vue consolidée du groupe";

  return (
    <div className="container mx-auto space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Button variant="ghost" size="sm" onClick={handleBack} className="mb-2">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Retour
          </Button>
          <h1 className={pageTitleClassName}>{groupTitle}</h1>
          <div className="flex flex-wrap items-center gap-3 text-muted-foreground mt-1 text-sm">
            {groupDetails?.siren ? (
              <span className="font-mono text-xs">SIREN {groupDetails.siren}</span>
            ) : null}
            <span className="flex items-center gap-1">
              <Building2 className="h-4 w-4" />
              {filteredTotals.company_count || stats?.metadata.company_count || 0} entreprise
              {(filteredTotals.company_count || 0) > 1 ? "s" : ""}
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <Calendar className="h-4 w-4" />
              {effectivePeriodLabel}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            onClick={() => void handleExportExcel()}
            variant="outline"
            disabled={!stats || isLoading || isExporting || noCompaniesSelected}
          >
            <Download className="h-4 w-4 mr-2" />
            {isExporting ? "Export en cours…" : "Exporter Excel"}
          </Button>
          <Button variant="outline" size="icon" onClick={copyShareLink} title="Copier le lien">
            <Link2 className="h-4 w-4" />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => loadStats()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Recharger
              </DropdownMenuItem>
              {isPlatformAdminUser && groupId ? (
                <DropdownMenuItem onClick={() => navigate(`/super-admin/groups/${groupId}`)}>
                  <Settings className="h-4 w-4 mr-2" />
                  Gérer le groupe
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {stats?.metadata.payroll_fallback_applied ? (
        <Alert>
          <AlertDescription>
            {stats.metadata.payroll_period_year && stats.metadata.payroll_period_month ? (
              <>
                Données paie affichées sur {effectivePeriodLabel}, dernière période disponible.
                {requestedPeriodLabel !== effectivePeriodLabel
                  ? ` ${requestedPeriodLabel} n'est pas encore importé.`
                  : null}
              </>
            ) : (
              <>
                Données paie issues des dernières périodes disponibles par entreprise.
                {requestedPeriodLabel
                  ? ` ${requestedPeriodLabel} n'est pas encore importé.`
                  : null}
              </>
            )}
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Filter className="h-5 w-5" />
            Filtres
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-3">
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">
              Période
            </Label>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(PRESET_LABELS) as PeriodPreset[])
                .filter((p) => p !== "custom")
                .map((preset) => (
                  <Button
                    key={preset}
                    type="button"
                    size="sm"
                    variant={period.preset === preset ? "default" : "outline"}
                    onClick={() => applyPeriodPreset(preset)}
                  >
                    {PRESET_LABELS[preset]}
                  </Button>
                ))}
              <Button
                type="button"
                size="sm"
                variant={period.preset === "custom" ? "default" : "outline"}
                onClick={() => setPeriod((p) => ({ ...p, preset: "custom" }))}
              >
                Personnaliser…
              </Button>
            </div>

            {period.preset === "custom" ? (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-2">
                <div className="space-y-2">
                  <Label>Type</Label>
                  <Select
                    value={period.mode}
                    onValueChange={(v) =>
                      setPeriod((p) => ({
                        ...p,
                        mode: v as PeriodState["mode"],
                        preset: "custom",
                      }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="month">Mensuelle</SelectItem>
                      <SelectItem value="year">Annuelle</SelectItem>
                      <SelectItem value="range">Pluriannuelle</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {period.mode === "month" ? (
                  <>
                    <div className="space-y-2">
                      <Label>Mois</Label>
                      <Select
                        value={String(period.month)}
                        onValueChange={(v) =>
                          setPeriod((p) => ({ ...p, month: Number(v), preset: "custom" }))
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: 12 }, (_, i) => i + 1).map((month) => (
                            <SelectItem key={month} value={String(month)}>
                              {formatMonthLabel(month)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Année</Label>
                      <Select
                        value={String(period.year)}
                        onValueChange={(v) =>
                          setPeriod((p) => ({ ...p, year: Number(v), preset: "custom" }))
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {yearOptions.map((year) => (
                            <SelectItem key={year} value={String(year)}>
                              {year}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </>
                ) : null}

                {period.mode === "year" ? (
                  <div className="space-y-2">
                    <Label>Année</Label>
                    <Select
                      value={String(period.year)}
                      onValueChange={(v) =>
                        setPeriod((p) => ({
                          ...p,
                          year: Number(v),
                          startYear: Number(v),
                          endYear: Number(v),
                          preset: "custom",
                        }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {yearOptions.map((year) => (
                          <SelectItem key={year} value={String(year)}>
                            {year}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ) : null}

                {period.mode === "range" ? (
                  <>
                    <div className="space-y-2">
                      <Label>Début</Label>
                      <Select
                        value={String(period.startYear)}
                        onValueChange={(v) =>
                          setPeriod((p) => ({ ...p, startYear: Number(v), preset: "custom" }))
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {yearOptions.map((year) => (
                            <SelectItem key={year} value={String(year)}>
                              {year}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Fin</Label>
                      <Select
                        value={String(period.endYear)}
                        onValueChange={(v) =>
                          setPeriod((p) => ({ ...p, endYear: Number(v), preset: "custom" }))
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {yearOptions.map((year) => (
                            <SelectItem key={year} value={String(year)}>
                              {year}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </>
                ) : null}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Label className="text-sm shrink-0">Comparer à</Label>
              <Select
                value={compareTo}
                onValueChange={(v) => setCompareTo(v as CompareToMode)}
              >
                <SelectTrigger className="w-[220px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="off">Aucune comparaison</SelectItem>
                  <SelectItem value="previous_month">Mois précédent</SelectItem>
                  <SelectItem value="previous_year">Année précédente</SelectItem>
                  <SelectItem value="ytd_previous_year">YTD année N-1</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2 border-t pt-4">
            <Label>
              Périmètre entreprises ({selectedCompanyIds.size}/{availableCompanies.length})
            </Label>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  if (selectedCompanyIds.size === availableCompanies.length) {
                    setSelectedCompanyIds(new Set());
                  } else {
                    setSelectedCompanyIds(
                      new Set(availableCompanies.map((c) => c.company_id)),
                    );
                  }
                }}
                className="h-8"
              >
                <CheckCircle2 className="h-3 w-3 mr-1" />
                {selectedCompanyIds.size === availableCompanies.length
                  ? "Tout désélectionner"
                  : "Tout sélectionner"}
              </Button>
              {availableCompanies.map((company) => (
                <Badge
                  key={company.company_id}
                  variant={selectedCompanyIds.has(company.company_id) ? "default" : "outline"}
                  className="cursor-pointer"
                  onClick={() => {
                    const next = new Set(selectedCompanyIds);
                    if (next.has(company.company_id)) next.delete(company.company_id);
                    else next.add(company.company_id);
                    setSelectedCompanyIds(next);
                  }}
                >
                  {company.company_name}
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {noCompaniesSelected ? (
        <Alert>
          <AlertDescription>
            Sélectionnez au moins une entreprise pour afficher les statistiques consolidées.
          </AlertDescription>
        </Alert>
      ) : null}

      {isLoading ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="p-4">
                  <Skeleton className="h-4 w-24 mb-2" />
                  <Skeleton className="h-8 w-32" />
                </CardContent>
              </Card>
            ))}
          </div>
          <SectionSkeleton />
        </div>
      ) : stats ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard
              label="Total employés"
              value={filteredTotals.total_employees}
              hint={`${filteredTotals.total_employees_excluding_rh} hors-RH · ${filteredTotals.total_rh} RH`}
              delta={
                kpiDeltas?.employees != null
                  ? { value: kpiDeltas.employees, worseIfPositive: false }
                  : undefined
              }
            />
            <KpiCard
              label="Coût employeur total"
              value={formatCompactNumber(totalEmployerCostValue)}
              hint={`${formatCompactNumber(avgGrossPerEmployee)} brut moy. / employé`}
              delta={
                kpiDeltas?.employerCost != null
                  ? { value: kpiDeltas.employerCost, worseIfPositive: true }
                  : undefined
              }
            />
            <KpiCard
              label="Masse salariale brute"
              value={formatCompactNumber(filteredTotals.total_gross_salary)}
              delta={
                kpiDeltas?.gross != null
                  ? { value: kpiDeltas.gross, worseIfPositive: true }
                  : undefined
              }
            />
            <KpiCard
              label="Charges patronales"
              value={formatCompactNumber(filteredTotals.total_employer_charges)}
              hint={`${chargeRate.toFixed(1)} % du brut`}
              delta={
                kpiDeltas?.charges != null
                  ? { value: kpiDeltas.charges, worseIfPositive: true }
                  : undefined
              }
            />
          </div>

          <Tabs defaultValue="table" className="space-y-4">
            <TabsList className="grid w-full min-w-0 grid-cols-2 md:grid-cols-4 gap-1">
              <TabsTrigger value="table">
                <ArrowUpDown className="h-4 w-4 mr-2" />
                Tableau
              </TabsTrigger>
              <TabsTrigger value="kpis">
                <Calculator className="h-4 w-4 mr-2" />
                KPIs & comparatifs
              </TabsTrigger>
              <TabsTrigger value="comparison">
                <PieChartIcon className="h-4 w-4 mr-2" />
                Répartition
              </TabsTrigger>
              <TabsTrigger value="evolution">
                <TrendingUp className="h-4 w-4 mr-2" />
                Évolutions
              </TabsTrigger>
            </TabsList>

            <TabsContent value="table" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <CardTitle>Détails par entreprise</CardTitle>
                      <CardDescription>
                        Cliquez sur une ligne pour ouvrir le tableau de bord de l&apos;entreprise
                      </CardDescription>
                    </div>
                    <Input
                      placeholder="Rechercher…"
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="max-w-xs"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handleExportTableExcel()}
                      disabled={
                        !stats ||
                        isLoading ||
                        isExportingTable ||
                        noCompaniesSelected ||
                        filteredAndSortedCompanies.length === 0
                      }
                    >
                      <Download className="h-4 w-4 mr-2" />
                      {isExportingTable ? "Export…" : "Exporter Excel"}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="w-full overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/50">
                          {(
                            [
                              ["company_name", "Entreprise", "left"],
                              ["employee_count", "Employés (hors-RH)", "right"],
                              ["rh_count", "RH", "right"],
                              ["payslip_count", "Bulletins", "right"],
                              ["gross_salary", "Masse brute", "right"],
                              [null, "Coût employeur", "right"],
                              ["net_salary", "Masse nette", "right"],
                              ["employer_charges", "Charges", "right"],
                            ] as const
                          ).map(([key, label, align]) => (
                            <th key={label} className={`p-3 text-${align}`}>
                              {key ? (
                                <button
                                  type="button"
                                  onClick={() => handleSort(key as SortKey)}
                                  className={`font-medium hover:underline flex items-center ${align === "right" ? "justify-end ml-auto" : ""}`}
                                >
                                  {label}
                                  <ArrowUpDown className="h-3 w-3 ml-1" />
                                </button>
                              ) : (
                                <span className="font-medium">{label}</span>
                              )}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {filteredAndSortedCompanies.map((company) => {
                          const employerCost =
                            company.gross_salary + company.employer_charges;
                          const companyChargeRate =
                            company.gross_salary > 0
                              ? (company.employer_charges / company.gross_salary) * 100
                              : 0;
                          const prevGross = companyGrossFromComparison(
                            stats.comparison,
                            company.company_id,
                          );
                          const grossDelta =
                            prevGross != null
                              ? percentDelta(company.gross_salary, prevGross)
                              : null;

                          return (
                            <tr
                              key={company.company_id}
                              className="border-b hover:bg-muted/40 transition-colors cursor-pointer"
                              onClick={() => handleCompanyRowClick(company.company_id)}
                            >
                              <td className="p-3">
                                <div className="font-medium">{company.company_name}</div>
                                {company.siret ? (
                                  <div className="text-xs text-muted-foreground font-mono">
                                    {company.siret}
                                  </div>
                                ) : null}
                              </td>
                              <td className="text-right p-3">
                                <div className="inline-flex flex-col items-end gap-1">
                                  <Badge variant="secondary">{company.employee_count}</Badge>
                                  {company.active_employee_count != null ? (
                                    <span className="text-[11px] leading-none text-muted-foreground">
                                      {company.active_employee_count} actifs
                                    </span>
                                  ) : null}
                                </div>
                              </td>
                              <td className="text-right p-3">
                                <Badge variant="outline">{company.rh_count}</Badge>
                              </td>
                              <td className="text-right p-3 font-medium">
                                {company.payslip_count}
                              </td>
                              <td className="text-right p-3">
                                <div className="font-medium">
                                  {formatCurrency(company.gross_salary)}
                                </div>
                                {company.payroll_source === 'dsn' ? (
                                  <div className="mt-1 flex justify-end">
                                    <PayrollSourceBadge
                                      source="dsn"
                                      sourceLabel={company.payroll_source_label}
                                      partial={company.payroll_partial}
                                    />
                                  </div>
                                ) : company.gross_salary <= 0 && company.employee_count > 0 ? (
                                  <div className="mt-1 flex justify-end">
                                    <PayrollSourceBadge source="none" />
                                  </div>
                                ) : null}
                                {grossDelta != null && compareTo !== "off" ? (
                                  <div
                                    className={`text-xs ${grossDelta >= 0 ? "text-emerald-600" : "text-red-600"}`}
                                  >
                                    {grossDelta >= 0 ? "+" : ""}
                                    {grossDelta.toFixed(1)} % vs période préc.
                                  </div>
                                ) : null}
                              </td>
                              <td className="text-right p-3 font-medium">
                                {formatCurrency(employerCost)}
                              </td>
                              <td className="text-right p-3 text-green-700">
                                {formatCurrency(company.net_salary)}
                              </td>
                              <td className="text-right p-3">
                                <div className={chargeRateColorClass(companyChargeRate)}>
                                  {formatCurrency(company.employer_charges)}
                                </div>
                                <div className="text-xs text-muted-foreground">
                                  {companyChargeRate.toFixed(1)} %
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                      <tfoot>
                        <tr className="border-t-2 font-bold bg-muted/50">
                          <td className="p-3">Total</td>
                          <td className="text-right p-3">
                            <div className="inline-flex flex-col items-end gap-1">
                              <span>{filteredTotals.total_employees_excluding_rh}</span>
                              {filteredTotals.total_active_employees_excluding_rh != null ? (
                                <span className="text-[11px] leading-none font-normal text-muted-foreground">
                                  {filteredTotals.total_active_employees_excluding_rh} actifs
                                </span>
                              ) : null}
                            </div>
                          </td>
                          <td className="text-right p-3">{filteredTotals.total_rh}</td>
                          <td className="text-right p-3">{filteredTotals.total_payslip_count}</td>
                          <td className="text-right p-3">
                            {formatCurrency(filteredTotals.total_gross_salary)}
                          </td>
                          <td className="text-right p-3">
                            {formatCurrency(totalEmployerCostValue)}
                          </td>
                          <td className="text-right p-3 text-green-700">
                            {formatCurrency(filteredTotals.total_net_salary)}
                          </td>
                          <td className="text-right p-3">
                            {formatCurrency(filteredTotals.total_employer_charges)}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="kpis" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Indicateurs par entreprise</CardTitle>
                  <CardDescription>Ratios et métriques stratégiques</CardDescription>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="text-left p-3">Entreprise</th>
                        <th className="text-right p-3">Taux charges</th>
                        <th className="text-right p-3">Rétention nette</th>
                        <th className="text-right p-3">Coût/employé</th>
                        <th className="text-right p-3">Masse/employé</th>
                        <th className="text-right p-3">Ratio RH</th>
                      </tr>
                    </thead>
                    <tbody>
                      {kpiRows.map((k) => (
                        <tr key={k.company_id} className="border-b">
                          <td className="p-3 font-medium">{k.company_name}</td>
                          <td
                            className={`text-right p-3 font-medium ${chargeRateColorClass(k.chargeRate)}`}
                          >
                            {k.chargeRate.toFixed(1)} %
                          </td>
                          <td className="text-right p-3 text-green-700">
                            {k.netRetentionRate.toFixed(1)} %
                          </td>
                          <td className="text-right p-3">
                            {formatCurrency(k.totalCostPerEmployee)}
                          </td>
                          <td className="text-right p-3">
                            {formatCurrency(k.grossPerEmployee)}
                          </td>
                          <td className="text-right p-3">{k.rhRatio.toFixed(1)} %</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Taux de charges</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart
                        data={kpiRows.map((k) => ({
                          name:
                            k.company_name.length > 12
                              ? `${k.company_name.slice(0, 12)}…`
                              : k.company_name,
                          rate: k.chargeRate,
                        }))}
                      >
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                        <XAxis dataKey="name" fontSize={11} angle={-35} textAnchor="end" height={70} />
                        <YAxis fontSize={12} />
                        <Tooltip formatter={(v: number) => `${v.toFixed(1)} %`} />
                        <Bar dataKey="rate" name="Taux">
                          {kpiRows.map((k) => (
                            <Cell
                              key={k.company_id}
                              fill={
                                k.chargeRate > 45
                                  ? "#ef4444"
                                  : k.chargeRate > 40
                                    ? "#f59e0b"
                                    : "#10b981"
                              }
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Coût total par employé</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart
                        data={kpiRows.map((k) => ({
                          name:
                            k.company_name.length > 12
                              ? `${k.company_name.slice(0, 12)}…`
                              : k.company_name,
                          cost: k.totalCostPerEmployee,
                        }))}
                      >
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                        <XAxis dataKey="name" fontSize={11} angle={-35} textAnchor="end" height={70} />
                        <YAxis tickFormatter={(v) => formatCompactNumber(v)} fontSize={12} />
                        <Tooltip formatter={(v: number) => formatCurrency(v)} />
                        <Bar dataKey="cost" fill="hsl(var(--primary))" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Comparaison masse & charges</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                        <XAxis dataKey="name" fontSize={11} />
                        <YAxis tickFormatter={(v) => formatCompactNumber(v)} fontSize={12} />
                        <Tooltip formatter={(v: number) => formatCurrency(v)} />
                        <Legend />
                        <Bar dataKey="grossSalary" name="Brut" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="charges" name="Charges" fill="#ef4444" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Effectifs hors-RH vs RH</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                        <XAxis dataKey="name" fontSize={11} />
                        <YAxis fontSize={12} />
                        <Legend />
                        <Bar dataKey="employees" name="Hors-RH" fill="#10b981" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="rh" name="RH" fill="#6b7280" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Distribution des KPIs</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                    {[
                      ["Taux de charges (%)", distCharge, (v: number) => `${v.toFixed(1)} %`],
                      ["Coût / employé", distCost, formatCurrency],
                      ["Ratio RH (%)", distRh, (v: number) => `${v.toFixed(1)} %`],
                      ["Masse / employé", distSalary, formatCurrency],
                    ].map(([title, dist, fmt]) => (
                      <div key={title as string} className="space-y-2">
                        <h3 className="font-semibold">{title as string}</h3>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Min</span>
                          <span>{(fmt as (n: number) => string)((dist as typeof distCharge).min)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Médiane</span>
                          <span>{(fmt as (n: number) => string)((dist as typeof distCharge).median)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Moyenne</span>
                          <span>{(fmt as (n: number) => string)((dist as typeof distCharge).avg)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Max</span>
                          <span>{(fmt as (n: number) => string)((dist as typeof distCharge).max)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="comparison" className="space-y-4">
              <div className="flex flex-wrap gap-2 mb-2">
                {(
                  [
                    ["employees", "Effectifs"],
                    ["gross", "Masse brute"],
                    ["cost", "Coût employeur"],
                  ] as const
                ).map(([key, label]) => (
                  <Button
                    key={key}
                    size="sm"
                    variant={distributionBase === key ? "default" : "outline"}
                    onClick={() => setDistributionBase(key)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Répartition</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {pieChartData.length > 0 ? (
                      <ResponsiveContainer width="100%" height={360}>
                        <PieChart>
                          <Pie
                            data={pieChartData}
                            cx="50%"
                            cy="45%"
                            labelLine
                            label={({ percent }) => `${(percent * 100).toFixed(1)} %`}
                            outerRadius={110}
                            dataKey="value"
                          >
                            {pieChartData.map((_, index) => (
                              <Cell key={index} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    ) : (
                      <p className="text-muted-foreground text-sm py-8 text-center">
                        Aucune donnée pour cette répartition
                      </p>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Synthèse groupe</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Taux de charges</span>
                      <span className={chargeRateColorClass(chargeRate)}>
                        {chargeRate.toFixed(1)} %
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Coût employeur total</span>
                      <span className="font-medium">{formatCurrency(totalEmployerCostValue)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Masse brute / employé</span>
                      <span className="font-medium">{formatCurrency(avgGrossPerEmployee)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Ratio RH</span>
                      <span className="font-medium">
                        {filteredTotals.total_employees > 0
                          ? (
                              (filteredTotals.total_rh / filteredTotals.total_employees) *
                              100
                            ).toFixed(1)
                          : 0}
                        %
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="evolution" className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant={evolutionView === "aggregate" ? "default" : "outline"}
                  onClick={() => setEvolutionView("aggregate")}
                >
                  Vue agrégée
                </Button>
                <Button
                  size="sm"
                  variant={evolutionView === "by_company" ? "default" : "outline"}
                  onClick={() => setEvolutionView("by_company")}
                >
                  Par entreprise
                </Button>
                {( ["gross", "charges", "total", "employees"] as const).map((m) => (
                  <Button
                    key={m}
                    size="sm"
                    variant={evolutionMetric === m ? "default" : "outline"}
                    onClick={() => setEvolutionMetric(m)}
                    disabled={evolutionView === "aggregate" && m === "employees"}
                  >
                    {m === "gross"
                      ? "Brut"
                      : m === "charges"
                        ? "Charges"
                        : m === "total"
                          ? "Coût total"
                          : "Effectifs"}
                  </Button>
                ))}
              </div>

              {evolutionChartData.data.length > 0 ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Évolution temporelle</CardTitle>
                    <CardDescription>{effectivePeriodLabel}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={400}>
                      {evolutionView === "aggregate" ? (
                        <AreaChart data={evolutionChartData.data}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis dataKey="month" fontSize={12} />
                          <YAxis tickFormatter={(v) => formatCompactNumber(v)} fontSize={12} />
                          <Tooltip formatter={(v: number) => formatCurrency(v)} />
                          <Legend />
                          <Area
                            type="monotone"
                            dataKey="gross"
                            stroke="#3b82f6"
                            fill="#3b82f640"
                            name="Masse brute"
                          />
                          <Area
                            type="monotone"
                            dataKey="charges"
                            stroke="#ef4444"
                            fill="#ef444440"
                            name="Charges"
                          />
                        </AreaChart>
                      ) : (
                        <LineChart data={evolutionChartData.data}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis dataKey="month" fontSize={12} />
                          <YAxis
                            tickFormatter={(v) =>
                              evolutionMetric === "employees"
                                ? String(v)
                                : formatCompactNumber(v)
                            }
                            fontSize={12}
                          />
                          <Tooltip
                            formatter={(v: number) =>
                              evolutionMetric === "employees"
                                ? String(v)
                                : formatCurrency(v)
                            }
                          />
                          <Legend />
                          {evolutionChartData.series.map((s, i) => (
                            <Line
                              key={s.id}
                              type="monotone"
                              dataKey={s.id}
                              name={s.name}
                              stroke={COLORS[i % COLORS.length]}
                              strokeWidth={2}
                              dot={false}
                            />
                          ))}
                        </LineChart>
                      )}
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              ) : (
                <Card>
                  <CardContent className="p-8 text-center text-muted-foreground">
                    Aucune donnée d&apos;évolution pour cette période
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          </Tabs>
        </>
      ) : (
        <Alert>
          <AlertDescription>Aucune statistique disponible</AlertDescription>
        </Alert>
      )}
    </div>
  );
}
