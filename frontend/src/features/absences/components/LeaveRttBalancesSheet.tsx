import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getLeaveBalancesOverview,
  updateEmployeeRttSolde,
  type LeaveBalanceOverviewItem,
} from '@/api/leaveSettings';
import { useCompany } from '@/contexts/CompanyContext';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
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
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';
import { Check, Loader2 } from 'lucide-react';

type RowDraft = {
  value: string;
  baseline: number;
};

function formatSolde(value: number): string {
  return value.toFixed(1);
}

function RttBalanceRow({
  employee,
  year,
  onSaved,
}: {
  employee: LeaveBalanceOverviewItem;
  year: number;
  onSaved: () => void;
}) {
  const { toast } = useToast();
  const baseline = employee.rtt_remaining;
  const [draft, setDraft] = useState<RowDraft>({
    value: formatSolde(baseline),
    baseline,
  });

  useEffect(() => {
    setDraft({ value: formatSolde(baseline), baseline });
  }, [baseline, employee.employee_id]);

  const dirty = draft.value !== formatSolde(draft.baseline);
  const hasAdjustment =
    Math.abs(employee.rtt_opening_balance ?? 0) > 0.001 || Boolean(employee.adjustment_note);

  const mutation = useMutation({
    mutationFn: () =>
      updateEmployeeRttSolde(employee.employee_id, year, {
        rtt_solde: parseFloat(draft.value) || 0,
      }),
    onSuccess: () => {
      onSaved();
      toast({
        title: 'Solde RTT enregistré',
        description: `${employee.first_name} ${employee.last_name}`,
      });
    },
    onError: () => {
      toast({
        title: 'Erreur',
        description: 'Impossible d’enregistrer le solde RTT.',
        variant: 'destructive',
      });
    },
  });

  const handleSave = () => {
    const parsed = parseFloat(draft.value);
    if (Number.isNaN(parsed) || parsed < 0) {
      toast({
        title: 'Valeur invalide',
        description: 'Saisissez un nombre de jours positif ou nul.',
        variant: 'destructive',
      });
      return;
    }
    mutation.mutate();
  };

  return (
    <TableRow>
      <TableCell>
        <div className="flex flex-wrap items-center gap-2">
          <span>
            {employee.first_name} {employee.last_name}
          </span>
          {hasAdjustment ? (
            <Badge variant="secondary" className="text-xs font-normal">
              ajusté
            </Badge>
          ) : null}
        </div>
      </TableCell>
      <TableCell className="w-[140px]">
        <Input
          type="number"
          min={0}
          step={0.5}
          value={draft.value}
          onChange={(e) => setDraft((prev) => ({ ...prev, value: e.target.value }))}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && dirty) {
              e.preventDefault();
              handleSave();
            }
          }}
          className="h-8 text-right tabular-nums"
          aria-label={`Solde RTT de ${employee.first_name} ${employee.last_name}`}
        />
      </TableCell>
      <TableCell className="w-[72px] text-right">
        <Button
          type="button"
          variant={dirty ? 'default' : 'ghost'}
          size="icon"
          className="h-8 w-8"
          disabled={!dirty || mutation.isPending}
          onClick={handleSave}
          aria-label={`Enregistrer le solde RTT de ${employee.first_name} ${employee.last_name}`}
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Check className="h-4 w-4" />
          )}
        </Button>
      </TableCell>
    </TableRow>
  );
}

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function LeaveRttBalancesSheet({ open, onOpenChange }: Props) {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [search, setSearch] = useState('');
  const queryClient = useQueryClient();

  useEffect(() => {
    if (open) {
      setYear(currentYear);
      setSearch('');
    }
  }, [open, currentYear]);

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.leaveBalancesOverview(companyId, year),
    queryFn: () => getLeaveBalancesOverview(year),
    enabled: Boolean(companyId) && open,
  });

  const employees = useMemo(() => {
    const rows = data?.employees ?? [];
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((emp) => {
      const name = `${emp.first_name} ${emp.last_name}`.toLowerCase();
      const email = (emp.email ?? '').toLowerCase();
      return name.includes(q) || email.includes(q);
    });
  }, [data?.employees, search]);

  const invalidateOverview = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.leaveBalancesOverview(companyId) });
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>Soldes RTT — effectif {year}</SheetTitle>
          <SheetDescription>
            Saisissez le solde RTT en jours pour chaque salarié. Les soldes CP restent gérés via
            l&apos;import bulletins ou les paramètres existants.
          </SheetDescription>
        </SheetHeader>

        <div className="mt-4 flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label htmlFor="rtt-balances-year">Année</Label>
            <Input
              id="rtt-balances-year"
              type="number"
              min={2020}
              max={2035}
              value={year}
              onChange={(e) => setYear(Number(e.target.value) || currentYear)}
              className="w-28"
            />
          </div>
          <div className="min-w-[180px] flex-1 space-y-1">
            <Label htmlFor="rtt-balances-search">Rechercher</Label>
            <Input
              id="rtt-balances-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Nom ou e-mail…"
            />
          </div>
        </div>

        <div className="mt-4 min-h-0 flex-1 overflow-auto rounded-md border">
          {isLoading ? (
            <p className="p-4 text-sm text-muted-foreground">Chargement…</p>
          ) : employees.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">Aucun salarié trouvé.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead className="text-right">Solde RTT (j)</TableHead>
                  <TableHead className="w-[72px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {employees.map((emp) => (
                  <RttBalanceRow
                    key={emp.employee_id}
                    employee={emp}
                    year={year}
                    onSaved={invalidateOverview}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
