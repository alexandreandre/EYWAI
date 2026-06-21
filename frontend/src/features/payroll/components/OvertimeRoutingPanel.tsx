import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import {
  listOvertimeRouting,
  upsertOvertimeRouting,
  type OvertimeRoutingRow,
} from '@/api/modulation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useToast } from '@/hooks/use-toast';

interface OvertimeRoutingPanelProps {
  year: number;
  month: number;
  className?: string;
}

export function OvertimeRoutingPanel({ year, month, className }: OvertimeRoutingPanelProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, { pay: string; account: string }>>({});

  const { data: rows = [], isLoading } = useQuery({
    queryKey: ['overtime-routing', year, month],
    queryFn: () => listOvertimeRouting(year, month),
    enabled: year > 0 && month > 0,
  });

  const saveMutation = useMutation({
    mutationFn: ({
      row,
      validate,
    }: {
      row: OvertimeRoutingRow;
      validate: boolean;
    }) => {
      const draft = drafts[row.employee_id] ?? {
        pay: String(row.hours_to_pay || row.total_hs_hours),
        account: String(row.hours_to_account || 0),
      };
      return upsertOvertimeRouting(row.employee_id, year, month, {
        hours_to_pay: Number(draft.pay) || 0,
        hours_to_account: Number(draft.account) || 0,
        submit_validated: validate,
      });
    },
    onSuccess: () => {
      toast({ title: 'Décision enregistrée' });
      queryClient.invalidateQueries({ queryKey: ['overtime-routing', year, month] });
      queryClient.invalidateQueries({ queryKey: ['preflight-anomalies'] });
    },
    onError: (err: Error) => {
      toast({ title: 'Erreur', description: err.message, variant: 'destructive' });
    },
  });

  if (isLoading) {
    return (
      <div className={className}>
        <Loader2 className="h-4 w-4 animate-spin" />
      </div>
    );
  }

  if (rows.length === 0) {
    return null;
  }

  const getDraft = (row: OvertimeRoutingRow) =>
    drafts[row.employee_id] ?? {
      pay: row.hours_to_pay > 0 ? String(row.hours_to_pay) : '',
      account:
        row.hours_to_account > 0
          ? String(row.hours_to_account)
          : row.status === 'pending'
            ? String(row.total_hs_hours)
            : '',
    };

  return (
    <div className={className}>
      <p className="mb-2 text-sm font-medium">Décisions HS — payer / compteur</p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Salarié</TableHead>
            <TableHead>Total HS</TableHead>
            <TableHead>À payer</TableHead>
            <TableHead>Au compteur</TableHead>
            <TableHead>Statut</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const draft = getDraft(row);
            return (
              <TableRow key={row.employee_id}>
                <TableCell>{row.employee_name}</TableCell>
                <TableCell>{row.total_hs_hours.toFixed(1)} h</TableCell>
                <TableCell>
                  <Input
                    type="number"
                    step={0.5}
                    min={0}
                    className="h-8 w-20"
                    value={draft.pay}
                    onChange={(e) =>
                      setDrafts((d) => ({
                        ...d,
                        [row.employee_id]: { ...draft, pay: e.target.value },
                      }))
                    }
                  />
                </TableCell>
                <TableCell>
                  <Input
                    type="number"
                    step={0.5}
                    min={0}
                    className="h-8 w-20"
                    value={draft.account}
                    onChange={(e) =>
                      setDrafts((d) => ({
                        ...d,
                        [row.employee_id]: { ...draft, account: e.target.value },
                      }))
                    }
                  />
                </TableCell>
                <TableCell className="text-sm capitalize">{row.status}</TableCell>
                <TableCell>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={saveMutation.isPending}
                    onClick={() => saveMutation.mutate({ row, validate: true })}
                  >
                    Valider
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
