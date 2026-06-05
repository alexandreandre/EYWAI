import { useEffect, useState, type ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import type { EmployeeListItem } from '@/hooks/queries/useEmployeesQuery';
import { CalendarDays, Rocket, Search } from 'lucide-react';
import {
  monthLabel,
  monthYearLabel,
  PAYROLL_MONTHS,
} from '@/features/payroll/utils/payrollMonth';
import {
  PayrollEmployeeListSkeleton,
  PayrollMonthListSkeleton,
} from '@/features/payroll/components/PayrollSkeletons';
import {
  PayrollPayslipRow,
  type PayslipRowState,
} from '@/features/payroll/components/PayrollPayslipRow';

export type EmployeeMonthState = {
  employee: EmployeeListItem;
  state: PayslipRowState;
};

export type PayrollMonthExplorerProps = {
  selectedYear: number;
  yearOptions: number[];
  onYearChange: (year: number) => void;
  selectedMonth: number;
  onSelectMonth: (month: number) => void;
  /** Nombre de bulletins générés par mois (clé = numéro de mois) pour l'année. */
  monthGeneratedCounts: Record<number, number>;
  /** Effectif total (pour les libellés « x / total »). */
  totalEmployees: number;
  /** Lignes collaborateurs pour le mois sélectionné. */
  employeeStates: EmployeeMonthState[];
  missingCount: number;
  onGenerateEmployee: (employeeId: string) => void;
  onGenerateMonth: () => void;
  onDeletePayslip: (payslipId: string, employeeId: string) => void;
  deletingPayslipId: string | null;
  loadingEmployees: boolean;
  loadingPayslips: boolean;
  progressSlot?: ReactNode;
};

function matchesSearch(emp: EmployeeListItem, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  const full = `${emp.first_name} ${emp.last_name}`.toLowerCase();
  const job = (emp.job_title ?? '').toLowerCase();
  return full.includes(needle) || job.includes(needle);
}

export function PayrollMonthExplorer({
  selectedYear,
  yearOptions,
  onYearChange,
  selectedMonth,
  onSelectMonth,
  monthGeneratedCounts,
  totalEmployees,
  employeeStates,
  missingCount,
  onGenerateEmployee,
  onGenerateMonth,
  onDeletePayslip,
  deletingPayslipId,
  loadingEmployees,
  loadingPayslips,
  progressSlot,
}: PayrollMonthExplorerProps) {
  const [search, setSearch] = useState('');
  const [mobileOpen, setMobileOpen] = useState(true);

  useEffect(() => {
    setSearch('');
  }, [selectedMonth, selectedYear]);

  const filtered = employeeStates.filter((row) => matchesSearch(row.employee, search));
  const generatedForMonth = monthGeneratedCounts[selectedMonth] ?? 0;

  const renderMonthButton = (month: number, variant: 'sidebar' | 'mobile') => {
    const isSelected = selectedMonth === month;
    const count = monthGeneratedCounts[month] ?? 0;

    return (
      <button
        type="button"
        key={month}
        onClick={() => {
          onSelectMonth(month);
          if (variant === 'mobile') setMobileOpen(false);
        }}
        className={cn(
          'flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-left text-sm transition-colors',
          isSelected
            ? 'bg-primary/10 text-primary font-medium'
            : 'text-foreground hover:bg-muted/80'
        )}
      >
        <CalendarDays className="h-4 w-4 shrink-0 opacity-70" aria-hidden />
        <span className="min-w-0 flex-1 truncate font-medium leading-tight">
          {monthLabel(month)}
        </span>
        <Badge variant="secondary" className="shrink-0 tabular-nums">
          {count}
        </Badge>
      </button>
    );
  };

  const searchField = (idSuffix: string) => (
    <div className="relative">
      <Search
        className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <Input
        id={`payroll-month-search-${idSuffix}`}
        type="search"
        placeholder="Rechercher un collaborateur…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="h-8 pl-8 text-sm"
        aria-label="Rechercher un collaborateur"
        disabled={loadingEmployees}
      />
    </div>
  );

  const yearControls = (
    <div className="flex flex-wrap items-center gap-2 shrink-0">
      <div className="flex items-center gap-2">
        <Label htmlFor="payroll-month-year-select" className="text-sm whitespace-nowrap">
          Année
        </Label>
        <Select value={String(selectedYear)} onValueChange={(v) => onYearChange(parseInt(v, 10))}>
          <SelectTrigger id="payroll-month-year-select" className="w-[110px] h-8">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {yearOptions.map((y) => (
              <SelectItem key={y} value={String(y)}>
                {y}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {missingCount > 0 && (
        <Button
          size="sm"
          variant="outline"
          className="gap-1.5"
          disabled={loadingPayslips || totalEmployees === 0}
          onClick={onGenerateMonth}
        >
          <Rocket className="h-3.5 w-3.5" />
          Générer le mois ({missingCount})
        </Button>
      )}
    </div>
  );

  const detailList =
    loadingPayslips ? (
      <PayrollMonthListSkeleton rows={Math.max(totalEmployees, 4)} />
    ) : filtered.length === 0 ? (
      <p className="px-3 py-8 text-center text-sm text-muted-foreground">
        {employeeStates.length === 0
          ? 'Aucun collaborateur à afficher.'
          : 'Aucun collaborateur trouvé.'}
      </p>
    ) : (
      <ul className="divide-y divide-border/60">
        {filtered.map(({ employee, state }) => (
          <PayrollPayslipRow
            key={employee.id}
            name={`${employee.first_name} ${employee.last_name}`}
            state={state}
            onGenerate={() => onGenerateEmployee(employee.id)}
            onDelete={(payslipId) => onDeletePayslip(payslipId, employee.id)}
            deletingPayslipId={deletingPayslipId}
            deleteDescription={
              <>
                Le bulletin de {employee.first_name} {employee.last_name} pour{' '}
                {monthYearLabel(selectedMonth, selectedYear)} sera supprimé définitivement.
              </>
            }
          />
        ))}
      </ul>
    );

  const detailSubtitle = (
    <p className="text-xs text-muted-foreground">
      {generatedForMonth} / {totalEmployees} bulletin{totalEmployees !== 1 ? 's' : ''} généré
      {generatedForMonth !== 1 ? 's' : ''}
    </p>
  );

  return (
    <div className="space-y-4">
      <Card className="hidden lg:block overflow-hidden">
        <div className="grid min-h-[420px] grid-cols-[minmax(200px,240px)_1fr]">
          <div className="border-r bg-muted/30 p-3 flex flex-col min-h-0">
            <p className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Mois {selectedYear}
            </p>
            <nav
              className="flex-1 space-y-0.5 overflow-y-auto max-h-[min(70vh,640px)]"
              aria-label="Liste des mois"
            >
              {PAYROLL_MONTHS.map((month) => renderMonthButton(month, 'sidebar'))}
            </nav>
          </div>

          <div className="flex flex-col min-w-0">
            <div className="space-y-2 border-b px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-semibold leading-tight">
                    {monthYearLabel(selectedMonth, selectedYear)}
                  </h3>
                  {detailSubtitle}
                </div>
                {yearControls}
              </div>
              <div className="pt-1">{searchField('desktop')}</div>
              {progressSlot}
            </div>
            <div className="flex-1 overflow-y-auto p-2 max-h-[min(70vh,640px)]">
              {loadingEmployees ? <PayrollEmployeeListSkeleton /> : detailList}
            </div>
          </div>
        </div>
      </Card>

      <div className="space-y-3 lg:hidden">
        <Card className="overflow-hidden">
          <CardHeader className="py-3">
            <button
              type="button"
              className="flex w-full items-center justify-between text-left"
              onClick={() => setMobileOpen((o) => !o)}
              aria-expanded={mobileOpen}
            >
              <CardTitle className="text-base font-semibold">
                {monthYearLabel(selectedMonth, selectedYear)}
              </CardTitle>
              <Badge variant="secondary">{generatedForMonth}</Badge>
            </button>
          </CardHeader>
          {mobileOpen && (
            <CardContent className="pt-0">
              <div className="grid grid-cols-3 gap-1.5">
                {PAYROLL_MONTHS.map((month) => renderMonthButton(month, 'mobile'))}
              </div>
            </CardContent>
          )}
        </Card>

        <Card>
          <CardHeader className="py-3 border-b space-y-2">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <CardTitle className="text-base">
                  {monthYearLabel(selectedMonth, selectedYear)}
                </CardTitle>
                {detailSubtitle}
              </div>
              {yearControls}
            </div>
            {searchField('mobile')}
            {progressSlot}
          </CardHeader>
          <CardContent className="pt-3">
            {loadingEmployees ? <PayrollEmployeeListSkeleton /> : detailList}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
