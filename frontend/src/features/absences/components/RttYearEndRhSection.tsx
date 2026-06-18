import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { closeRttYearEnd, getRttYearEndOverview } from '@/api/leaveSettings';
import { useCompany } from '@/contexts/CompanyContext';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
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
import { AlertTriangle } from 'lucide-react';

export function RttYearEndRhSection() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const year = new Date().getFullYear();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.rttYearEndOverview(companyId, year),
    queryFn: () => getRttYearEndOverview(year),
    enabled: Boolean(companyId),
  });

  const closable = useMemo(
    () => (data?.employees ?? []).filter((e) => e.closure_required),
    [data],
  );

  const mutation = useMutation({
    mutationFn: () => closeRttYearEnd(year, Array.from(selected)),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.rttYearEndOverview(companyId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.leaveBalancesOverview(companyId) });
      setSelected(new Set());
      toast({
        title: 'Clôture RTT enregistrée',
        description: `${result.closed_count} salarié(s) — ${result.total_days_forfeited} j perdus`,
      });
    },
    onError: () => {
      toast({ title: 'Erreur lors de la clôture', variant: 'destructive' });
    },
  });

  const toggleAll = (checked: boolean) => {
    if (checked) {
      setSelected(new Set(closable.map((e) => e.employee_id)));
    } else {
      setSelected(new Set());
    }
  };

  const toggleOne = (id: string, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  if (!data?.reminder_active && closable.length === 0 && !isLoading) {
    return null;
  }

  return (
    <Card className="border-amber-200">
      <CardHeader>
        <CardTitle className="text-base">Clôture RTT — fin d&apos;année {year}</CardTitle>
        <CardDescription>
          Validez la perte des RTT non posés au 31/12 (sans report).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {data?.reminder_active ? (
          <Alert className="border-amber-200 bg-amber-50/80">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <AlertTitle>Rappel fin d&apos;année</AlertTitle>
            <AlertDescription>
              {closable.length} salarié(s) ont encore des RTT à solder avant le 31/12.
            </AlertDescription>
          </Alert>
        ) : null}

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : closable.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun RTT restant à clôturer.</p>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      checked={
                        selected.size === closable.length && closable.length > 0
                      }
                      onCheckedChange={(v) => toggleAll(v === true)}
                    />
                  </TableHead>
                  <TableHead>Salarié</TableHead>
                  <TableHead className="text-right">RTT restants</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {closable.map((emp) => (
                  <TableRow key={emp.employee_id}>
                    <TableCell>
                      <Checkbox
                        checked={selected.has(emp.employee_id)}
                        onCheckedChange={(v) => toggleOne(emp.employee_id, v === true)}
                      />
                    </TableCell>
                    <TableCell>
                      {emp.first_name} {emp.last_name}
                    </TableCell>
                    <TableCell className="text-right">{emp.rtt_remaining.toFixed(1)} j</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Button
              variant="destructive"
              disabled={selected.size === 0 || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              Valider la perte des RTT sélectionnés
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
