import { useEffect, useState, type ReactNode } from 'react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
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
import { Rocket, Search, Users } from 'lucide-react';
import {
  PayrollEmployeeListSkeleton,
  PayrollMonthListSkeleton,
} from '@/features/payroll/components/PayrollSkeletons';

export type PayrollEmployeeExplorerProps = {
  employees: EmployeeListItem[];
  selectedEmployeeId: string | null;
  onSelectEmployee: (id: string) => void;
  yearCounts: Record<string, number>;
  selectedYear: number;
  yearOptions: number[];
  onYearChange: (year: number) => void;
  missingMonthsCount: number;
  onGenerateYear: () => void;
  detailLoading?: boolean;
  loadingEmployees: boolean;
  progressSlot?: ReactNode;
  renderDetail: () => ReactNode;
};

function employeeInitials(first: string, last: string): string {
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}

function matchesSearch(emp: EmployeeListItem, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  const full = `${emp.first_name} ${emp.last_name}`.toLowerCase();
  const job = (emp.job_title ?? '').toLowerCase();
  return full.includes(needle) || job.includes(needle);
}

export function PayrollEmployeeExplorer({
  employees,
  selectedEmployeeId,
  onSelectEmployee,
  yearCounts,
  selectedYear,
  yearOptions,
  onYearChange,
  missingMonthsCount,
  onGenerateYear,
  detailLoading = false,
  loadingEmployees,
  progressSlot,
  renderDetail,
}: PayrollEmployeeExplorerProps) {
  const [search, setSearch] = useState('');
  const [mobileOpen, setMobileOpen] = useState(true);

  const filtered = employees.filter((e) => matchesSearch(e, search));
  const selected = employees.find((e) => e.id === selectedEmployeeId);

  useEffect(() => {
    setSearch('');
  }, [selectedYear]);

  const renderEmployeeButton = (
    emp: EmployeeListItem,
    variant: 'sidebar' | 'mobile'
  ) => {
    const isSelected = selectedEmployeeId === emp.id;
    const count = yearCounts[emp.id] ?? 0;

    return (
      <button
        type="button"
        key={emp.id}
        onClick={() => {
          onSelectEmployee(emp.id);
          if (variant === 'mobile') setMobileOpen(false);
        }}
        className={cn(
          'flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-left text-sm transition-colors',
          isSelected
            ? 'bg-primary/10 text-primary font-medium'
            : 'text-foreground hover:bg-muted/80'
        )}
      >
        <Avatar className="h-7 w-7 shrink-0">
          <AvatarFallback className="text-xs">
            {employeeInitials(emp.first_name, emp.last_name)}
          </AvatarFallback>
        </Avatar>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium leading-tight">
            {emp.first_name} {emp.last_name}
          </span>
          {emp.job_title && (
            <span className="block truncate text-xs text-muted-foreground font-normal">
              {emp.job_title}
            </span>
          )}
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
        id={`payroll-employee-search-${idSuffix}`}
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

  const emptyDetail = (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center text-muted-foreground">
      <Users className="h-10 w-10 mb-3 opacity-40" aria-hidden />
      <p className="text-sm font-medium text-foreground">Sélectionnez un collaborateur</p>
      <p className="text-xs mt-1 max-w-xs">
        Choisissez un salarié dans la liste pour gérer et générer ses bulletins mensuels.
      </p>
    </div>
  );

  const detailContent =
    loadingEmployees && !selectedEmployeeId ? (
      <PayrollMonthListSkeleton />
    ) : selectedEmployeeId ? (
      renderDetail()
    ) : (
      emptyDetail
    );

  const bulletinCount = yearCounts[selectedEmployeeId ?? ''] ?? 0;

  const yearControls = selectedEmployeeId ? (
    <div className="flex flex-wrap items-center gap-2 shrink-0">
      <div className="flex items-center gap-2">
        <Label htmlFor="payroll-year-select" className="text-sm whitespace-nowrap">
          Année
        </Label>
        <Select
          value={String(selectedYear)}
          onValueChange={(v) => onYearChange(parseInt(v, 10))}
        >
          <SelectTrigger id="payroll-year-select" className="w-[110px] h-8">
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
      {missingMonthsCount > 0 && (
        <Button
          size="sm"
          variant="outline"
          className="gap-1.5"
          disabled={detailLoading}
          onClick={onGenerateYear}
        >
          <Rocket className="h-3.5 w-3.5" />
          Générer l&apos;année ({missingMonthsCount})
        </Button>
      )}
    </div>
  ) : null;

  return (
    <div className="space-y-4">
      <Card className="hidden lg:block overflow-hidden">
        <div className="grid min-h-[420px] grid-cols-[minmax(240px,280px)_1fr]">
          <div className="border-r bg-muted/30 p-3 flex flex-col min-h-0">
            <p className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Collaborateurs
            </p>
            <div className="mb-2 px-1">{searchField('desktop')}</div>
            <nav
              className="flex-1 space-y-0.5 overflow-y-auto max-h-[min(70vh,640px)]"
              aria-label="Liste des collaborateurs"
            >
              {loadingEmployees ? (
                <PayrollEmployeeListSkeleton />
              ) : filtered.length === 0 ? (
                <p className="px-3 py-4 text-sm text-muted-foreground">Aucun collaborateur trouvé.</p>
              ) : (
                filtered.map((emp) => renderEmployeeButton(emp, 'sidebar'))
              )}
            </nav>
          </div>

          <div className="flex flex-col min-w-0">
            <div className="space-y-2 border-b px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-semibold leading-tight">
                    {selected
                      ? `${selected.first_name} ${selected.last_name}`
                      : 'Bulletins de paie'}
                  </h3>
                  {selected && (
                    <p className="text-xs text-muted-foreground">
                      {bulletinCount} bulletin{bulletinCount !== 1 ? 's' : ''} en {selectedYear}
                    </p>
                  )}
                </div>
                {yearControls}
              </div>
              {progressSlot}
            </div>
            <div className="flex-1 overflow-y-auto p-2 max-h-[min(70vh,640px)]">
              {detailContent}
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
                {selected
                  ? `${selected.first_name} ${selected.last_name}`
                  : 'Collaborateurs'}
              </CardTitle>
              <Badge variant="secondary">{employees.length}</Badge>
            </button>
          </CardHeader>
          {mobileOpen && (
            <CardContent className="pt-0 space-y-2">
              {searchField('mobile')}
              <div className="max-h-48 overflow-y-auto space-y-0.5">
                {loadingEmployees ? (
                  <PayrollEmployeeListSkeleton rows={4} />
                ) : (
                  filtered.map((emp) => renderEmployeeButton(emp, 'mobile'))
                )}
              </div>
            </CardContent>
          )}
        </Card>

        <Card>
          <CardHeader className="py-3 border-b space-y-2">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <CardTitle className="text-base">
                  {selected
                    ? `${selected.first_name} ${selected.last_name}`
                    : `Bulletins ${selectedYear}`}
                </CardTitle>
                {selected && (
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {bulletinCount} bulletin{bulletinCount !== 1 ? 's' : ''} en {selectedYear}
                  </p>
                )}
              </div>
              {yearControls}
            </div>
            {progressSlot}
          </CardHeader>
          <CardContent className="pt-3">{detailContent}</CardContent>
        </Card>
      </div>
    </div>
  );
}
