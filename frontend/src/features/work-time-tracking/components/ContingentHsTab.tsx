import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getContingentEmployeeDetail,
  getContingentOverview,
  updateEmployeeContingentAdjustment,
  type ContingentOverviewRow,
} from '@/api/overtimeContingent';
import { PageFetchIndicator } from '@/components/skeletons/PageFetchIndicator';
import { TableSkeleton } from '@/components/skeletons/TableSkeleton';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Textarea } from '@/components/ui/textarea';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';
import { ContingentUsageBar } from '@/features/overtime-contingent/components/ContingentUsageBar';
import {
  CONTINGENT_STATUS_LABELS,
  formatHours,
  getContingentStatusVariant,
  matchesContingentFilter,
  type ContingentFilter,
} from '@/features/overtime-contingent/lib/contingentStatus';
import { workTimeHubPath } from '@/features/work-time-tracking/lib/workTimeTabRouting';
import { cn } from '@/lib/utils';
import { ArrowRight, Info, Search, UserMinus } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { isPayrollFocusActive } from '@/lib/payrollFocus';

const MONTH_LABELS = [
  'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
  'Juil', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc',
];

function KpiCard({
  title,
  value,
  active,
  onClick,
  variant = 'default',
}: {
  title: string;
  value: number;
  active: boolean;
  onClick: () => void;
  variant?: 'default' | 'warning' | 'danger';
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-lg border p-4 text-left transition-colors hover:bg-muted/50',
        active && 'ring-2 ring-primary border-primary',
        variant === 'danger' && 'border-destructive/40',
        variant === 'warning' && 'border-amber-500/40',
      )}
    >
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
    </button>
  );
}

function BreakdownTooltip({ row }: { row: ContingentOverviewRow }) {
  return (
    <div className="space-y-1 text-xs">
      <p>Structurelles : {formatHours(row.structural_hours)}</p>
      <p>Payées : {formatHours(row.paid_hours)}</p>
      <p>Pauses : −{formatHours(row.pause_deduction)}</p>
      <p>Ajustement : {formatHours(row.manual_adjustment)}</p>
      <p className="font-medium">Comptabilisées : {formatHours(row.consumed_hours)}</p>
    </div>
  );
}

function EmploymentStatusBadges({ status }: { status?: string | null }) {
  return (
    <>
      {status === 'en_onboarding' && (
        <Badge variant="outline" className="text-xs bg-amber-50 text-amber-800 border-amber-200">
          Onboarding
        </Badge>
      )}
      {status === 'en_sortie' && (
        <Badge variant="outline" className="text-xs flex items-center gap-1 bg-amber-50 text-amber-900 border-amber-200">
          <UserMinus className="h-3 w-3" />
          Départ à finaliser
        </Badge>
      )}
      {status === 'parti' && (
        <Badge variant="secondary" className="text-xs">
          Parti
        </Badge>
      )}
    </>
  );
}

export interface ContingentHsTabProps {
  initialEmployeeId?: string | null;
  onEmployeeSelect?: (employeeId: string | null) => void;
  hourAccountEnabled?: boolean;
}

export function ContingentHsTab({
  initialEmployeeId = null,
  onEmployeeSelect,
  hourAccountEnabled = false,
}: ContingentHsTabProps) {
  const companyId = useActiveCompanyId();
  const { user } = useAuth();
  const payrollFocus = isPayrollFocusActive(user);
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [referenceDate, setReferenceDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<ContingentFilter>('all');
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(
    initialEmployeeId,
  );
  const [adjustmentHours, setAdjustmentHours] = useState('0');
  const [adjustmentNote, setAdjustmentNote] = useState('');

  useEffect(() => {
    setSelectedEmployeeId(initialEmployeeId);
  }, [initialEmployeeId]);

  const overviewQuery = useQuery({
    queryKey: queryKeys.overtimeContingentOverview(companyId, year, referenceDate),
    queryFn: () => getContingentOverview({ year, reference_date: referenceDate }),
    enabled: Boolean(companyId),
  });

  const detailQuery = useQuery({
    queryKey: queryKeys.overtimeContingentDetail(
      companyId,
      selectedEmployeeId ?? '',
      year,
      referenceDate,
    ),
    queryFn: () =>
      getContingentEmployeeDetail(selectedEmployeeId!, {
        year,
        reference_date: referenceDate,
      }),
    enabled: Boolean(companyId && selectedEmployeeId),
  });

  const adjustmentMutation = useMutation({
    mutationFn: () =>
      updateEmployeeContingentAdjustment(selectedEmployeeId!, {
        year,
        opening_balance_hours: parseFloat(adjustmentHours) || 0,
        note: adjustmentNote || null,
      }),
    onSuccess: () => {
      toast({ title: 'Ajustement enregistré' });
      queryClient.invalidateQueries({
        queryKey: queryKeys.overtimeContingentOverview(companyId, year, referenceDate),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.overtimeContingentDetail(
          companyId,
          selectedEmployeeId ?? '',
          year,
          referenceDate,
        ),
      });
    },
    onError: () => {
      toast({
        title: 'Erreur',
        description: 'Impossible d’enregistrer l’ajustement.',
        variant: 'destructive',
      });
    },
  });

  const filteredRows = useMemo(() => {
    const rows = overviewQuery.data?.employees ?? [];
    const q = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (!matchesContingentFilter(row.status, filter)) return false;
      if (!q) return true;
      const name = `${row.first_name} ${row.last_name}`.toLowerCase();
      return name.includes(q);
    });
  }, [overviewQuery.data?.employees, search, filter]);

  const openDetail = (employeeId: string) => {
    setSelectedEmployeeId(employeeId);
    onEmployeeSelect?.(employeeId);
  };

  const closeDetail = () => {
    setSelectedEmployeeId(null);
    onEmployeeSelect?.(null);
  };

  const detail = detailQuery.data;
  const selectedRow = overviewQuery.data?.employees.find(
    (e) => e.employee_id === selectedEmployeeId,
  );

  useEffect(() => {
    if (detail) {
      setAdjustmentHours(String(detail.adjustment.opening_balance_hours));
      setAdjustmentNote(detail.adjustment.note ?? '');
    }
  }, [detail]);

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1">
            <Label htmlFor="contingent-year">Année</Label>
            <Input
              id="contingent-year"
              type="number"
              min={2020}
              max={2030}
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="w-28"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="contingent-ref">Date de référence</Label>
            <Input
              id="contingent-ref"
              type="date"
              value={referenceDate}
              onChange={(e) => setReferenceDate(e.target.value)}
              className="w-44"
            />
          </div>
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Rechercher un salarié…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        <PageFetchIndicator isFetching={overviewQuery.isFetching && !overviewQuery.isLoading} />

        {overviewQuery.isLoading ? (
          <TableSkeleton rows={6} columns={6} />
        ) : overviewQuery.isError ? (
          <Card>
            <CardContent className="py-8 text-center text-destructive">
              Impossible de charger le suivi contingent.
            </CardContent>
          </Card>
        ) : (
          <>
            {!payrollFocus && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard
                title="Salariés suivis"
                value={overviewQuery.data?.kpis.total_employees ?? 0}
                active={filter === 'all'}
                onClick={() => setFilter('all')}
              />
              <KpiCard
                title="Proche du plafond"
                value={overviewQuery.data?.kpis.near_limit_count ?? 0}
                active={filter === 'near_limit'}
                onClick={() => setFilter('near_limit')}
                variant="warning"
              />
              <KpiCard
                title="Plafond dépassé"
                value={overviewQuery.data?.kpis.management_exceeded_count ?? 0}
                active={filter === 'management_exceeded'}
                onClick={() => setFilter('management_exceeded')}
                variant="danger"
              />
              <KpiCard
                title="Seuil COR dépassé"
                value={overviewQuery.data?.kpis.cor_exceeded_count ?? 0}
                active={filter === 'cor_exceeded'}
                onClick={() => setFilter('cor_exceeded')}
                variant="danger"
              />
            </div>
            )}

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">
                  Plafond gestion :{' '}
                  {formatHours(
                    overviewQuery.data?.settings.management_contingent_hours ??
                      overviewQuery.data?.settings.legal_cor_contingent_hours ??
                      360,
                  )}
                  {' · '}
                  COR légal :{' '}
                  {formatHours(overviewQuery.data?.settings.legal_cor_contingent_hours ?? 220)}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Salarié</TableHead>
                      <TableHead>Utilisation plafond</TableHead>
                      <TableHead>HS comptabilisées</TableHead>
                      <TableHead>RCR posées</TableHead>
                      <TableHead>Marge restante</TableHead>
                      <TableHead>Statut</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredRows.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                          Aucun salarié pour ce filtre.
                        </TableCell>
                      </TableRow>
                    ) : (
                      filteredRows.map((row) => (
                        <TableRow
                          key={row.employee_id}
                          className="cursor-pointer hover:bg-muted/40"
                          onClick={() => openDetail(row.employee_id)}
                        >
                          <TableCell className="font-medium">
                            <div className="flex items-center gap-2">
                              <span>
                                {row.last_name} {row.first_name}
                              </span>
                              <EmploymentStatusBadges status={row.employment_status} />
                            </div>
                          </TableCell>
                          <TableCell>
                            <ContingentUsageBar usagePercent={row.usage_percent} />
                          </TableCell>
                          <TableCell>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="inline-flex items-center gap-1 tabular-nums">
                                  {formatHours(row.consumed_hours)}
                                  <Info className="h-3.5 w-3.5 text-muted-foreground" />
                                </span>
                              </TooltipTrigger>
                              <TooltipContent side="right">
                                <BreakdownTooltip row={row} />
                              </TooltipContent>
                            </Tooltip>
                          </TableCell>
                          <TableCell className="tabular-nums">{formatHours(row.rcr_hours)}</TableCell>
                          <TableCell
                            className={cn(
                              'tabular-nums font-medium',
                              row.margin_hours < 0 && 'text-destructive',
                            )}
                          >
                            {formatHours(row.margin_hours)}
                          </TableCell>
                          <TableCell>
                            <Badge variant={getContingentStatusVariant(row.status)}>
                              {CONTINGENT_STATUS_LABELS[row.status]}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </>
        )}

        <Sheet
          open={Boolean(selectedEmployeeId)}
          onOpenChange={(open) => {
            if (!open) closeDetail();
          }}
        >
          <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
            {selectedRow && (
              <>
                <SheetHeader>
                  <SheetTitle>
                    <span className="inline-flex items-center gap-2">
                      {selectedRow.last_name} {selectedRow.first_name}
                      <EmploymentStatusBadges status={selectedRow.employment_status} />
                    </span>
                  </SheetTitle>
                  <SheetDescription>
                    Détail contingent {year} au {referenceDate}
                  </SheetDescription>
                </SheetHeader>

                <div className="mt-6 space-y-6">
                  <ContingentUsageBar usagePercent={selectedRow.usage_percent} />

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-md border p-3">
                      <p className="text-muted-foreground">HS comptabilisées</p>
                      <p className="font-semibold tabular-nums">
                        {formatHours(selectedRow.consumed_hours)}
                      </p>
                    </div>
                    <div className="rounded-md border p-3">
                      <p className="text-muted-foreground">Marge restante</p>
                      <p
                        className={cn(
                          'font-semibold tabular-nums',
                          selectedRow.margin_hours < 0 && 'text-destructive',
                        )}
                      >
                        {formatHours(selectedRow.margin_hours)}
                      </p>
                    </div>
                    <div className="rounded-md border p-3">
                      <p className="text-muted-foreground">RCR posées</p>
                      <p className="font-semibold tabular-nums">
                        {formatHours(selectedRow.rcr_hours)}
                      </p>
                    </div>
                    <div className="rounded-md border p-3">
                      <p className="text-muted-foreground">Excédent COR</p>
                      <p className="font-semibold tabular-nums">
                        {formatHours(selectedRow.legal_cor_excess)}
                      </p>
                    </div>
                  </div>

                  {detailQuery.isLoading ? (
                    <p className="text-sm text-muted-foreground">Chargement du détail…</p>
                  ) : detail ? (
                    <>
                      <div>
                        <h4 className="text-sm font-semibold mb-2">Évolution mensuelle</h4>
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Mois</TableHead>
                              <TableHead>HS payées</TableHead>
                              <TableHead>Cumul</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {detail.monthly.map((m) => (
                              <TableRow key={m.month}>
                                <TableCell>{MONTH_LABELS[m.month - 1]}</TableCell>
                                <TableCell className="tabular-nums">
                                  {formatHours(m.paid_hours)}
                                </TableCell>
                                <TableCell className="tabular-nums">
                                  {formatHours(m.cumulative_total)}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>

                      <div className="space-y-3 rounded-lg border p-4">
                        <h4 className="text-sm font-semibold">Ajustement manuel (report N−1)</h4>
                        <div className="space-y-2">
                          <Label htmlFor="adj-hours">Heures reportées</Label>
                          <Input
                            id="adj-hours"
                            type="number"
                            step="0.01"
                            value={adjustmentHours}
                            onChange={(e) => setAdjustmentHours(e.target.value)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="adj-note">Note</Label>
                          <Textarea
                            id="adj-note"
                            rows={2}
                            value={adjustmentNote}
                            onChange={(e) => setAdjustmentNote(e.target.value)}
                          />
                        </div>
                        <Button
                          size="sm"
                          disabled={adjustmentMutation.isPending}
                          onClick={() => adjustmentMutation.mutate()}
                        >
                          Enregistrer l’ajustement
                        </Button>
                      </div>
                    </>
                  ) : null}

                  <div className="flex flex-col gap-2">
                    {hourAccountEnabled && selectedEmployeeId && (
                      <Button variant="outline" size="sm" asChild>
                        <Link
                          to={workTimeHubPath({
                            tab: 'compte-heures',
                            employee: selectedEmployeeId,
                          })}
                        >
                          Voir le solde compte d&apos;heures
                          <ArrowRight className="ml-2 h-4 w-4" />
                        </Link>
                      </Button>
                    )}
                    <Button variant="outline" size="sm" asChild>
                      <Link to={`/employees/${selectedEmployeeId}`}>Voir la fiche employé</Link>
                    </Button>
                  </div>
                </div>
              </>
            )}
          </SheetContent>
        </Sheet>
      </div>
    </TooltipProvider>
  );
}
