import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getLeaveBalancesOverview,
  importLeaveAdjustments,
  updateEmployeeLeaveAdjustment,
  type LeaveAdjustmentImportRow,
  type LeaveBalanceOverviewItem,
} from '@/api/leaveSettings';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';
import { Upload } from 'lucide-react';

function parseCsv(text: string): LeaveAdjustmentImportRow[] {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];
  const header = lines[0].toLowerCase();
  const sep = header.includes(';') ? ';' : ',';
  const cols = lines[0].split(sep).map((c) => c.trim().toLowerCase());
  const idx = (names: string[]) =>
    cols.findIndex((c) => names.some((n) => c.includes(n)));

  const emailI = idx(['email']);
  const fnI = idx(['prenom', 'first']);
  const lnI = idx(['nom', 'last']);
  const cpN1I = idx(['cp_n1', 'n-1', 'report']);
  const cpNI = idx(['cp_n', 'n_solde', 'courant']);
  const rttI = idx(['rtt']);
  const yearI = idx(['annee', 'year']);

  const rows: LeaveAdjustmentImportRow[] = [];
  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(sep).map((p) => p.trim());
    const year = yearI >= 0 ? parseInt(parts[yearI], 10) : new Date().getFullYear();
    rows.push({
      email: emailI >= 0 ? parts[emailI] : undefined,
      first_name: fnI >= 0 ? parts[fnI] : undefined,
      last_name: lnI >= 0 ? parts[lnI] : undefined,
      cp_n1_solde: cpN1I >= 0 ? parseFloat(parts[cpN1I]) || 0 : 0,
      cp_n_solde: cpNI >= 0 ? parseFloat(parts[cpNI]) || 0 : 0,
      rtt_solde: rttI >= 0 ? parseFloat(parts[rttI]) || 0 : 0,
      year: Number.isFinite(year) ? year : new Date().getFullYear(),
    });
  }
  return rows;
}

function AdjustmentDialog({
  employee,
  year,
  open,
  onOpenChange,
}: {
  employee: LeaveBalanceOverviewItem;
  year: number;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';

  const [cpN1, setCpN1] = useState('0');
  const [cpN, setCpN] = useState('0');
  const [rtt, setRtt] = useState('0');
  const [note, setNote] = useState('');

  const mutation = useMutation({
    mutationFn: () =>
      updateEmployeeLeaveAdjustment(employee.employee_id, year, {
        cp_n1_opening_balance: parseFloat(cpN1) || 0,
        cp_n_opening_balance: parseFloat(cpN) || 0,
        rtt_opening_balance: parseFloat(rtt) || 0,
        note: note || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.leaveBalancesOverview(companyId) });
      toast({ title: 'Solde enregistré' });
      onOpenChange(false);
    },
    onError: () => {
      toast({ title: 'Erreur', variant: 'destructive' });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Ajuster — {employee.first_name} {employee.last_name}
          </DialogTitle>
        </DialogHeader>
        <div className="grid gap-3">
          <div>
            <Label>Ajustement CP report N-1 (+/− jours)</Label>
            <Input value={cpN1} onChange={(e) => setCpN1(e.target.value)} type="number" step="0.5" />
          </div>
          <div>
            <Label>Ajustement CP période en cours (+/− jours)</Label>
            <Input value={cpN} onChange={(e) => setCpN(e.target.value)} type="number" step="0.5" />
          </div>
          <div>
            <Label>Ajustement RTT (+/− jours)</Label>
            <Input value={rtt} onChange={(e) => setRtt(e.target.value)} type="number" step="0.5" />
          </div>
          <div>
            <Label>Note</Label>
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function LeaveBalancesRhSection() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const year = new Date().getFullYear();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [adjustTarget, setAdjustTarget] = useState<LeaveBalanceOverviewItem | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.leaveBalancesOverview(companyId, year),
    queryFn: () => getLeaveBalancesOverview(year),
    enabled: Boolean(companyId),
  });

  const importMutation = useMutation({
    mutationFn: importLeaveAdjustments,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.leaveBalancesOverview(companyId) });
      toast({
        title: 'Import terminé',
        description: `${result.imported} ligne(s) importée(s)${
          result.errors.length ? ` — ${result.errors.length} erreur(s)` : ''
        }`,
        variant: result.errors.length ? 'destructive' : 'default',
      });
    },
  });

  const handleFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      const rows = parseCsv(String(reader.result ?? ''));
      if (!rows.length) {
        toast({ title: 'Fichier vide ou invalide', variant: 'destructive' });
        return;
      }
      importMutation.mutate(rows);
    };
    reader.readAsText(file);
  };

  const employees = useMemo(() => data?.employees ?? [], [data]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="text-base">Soldes congés &amp; RTT</CardTitle>
          <CardDescription>
            Vue effectif {year} — ajustements manuels ou import CSV (email, cp_n1, cp_n, rtt,
            annee).
          </CardDescription>
        </div>
        <label className="cursor-pointer">
          <input
            type="file"
            accept=".csv,.txt"
            className="sr-only"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
              e.target.value = '';
            }}
          />
          <Button variant="outline" size="sm" asChild>
            <span>
              <Upload className="mr-2 h-4 w-4" />
              Import CSV
            </span>
          </Button>
        </label>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Salarié</TableHead>
                <TableHead className="text-right">CP N-1</TableHead>
                <TableHead className="text-right">CP N</TableHead>
                <TableHead className="text-right">CP total</TableHead>
                <TableHead className="text-right">CP anc.</TableHead>
                <TableHead className="text-right">RTT</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {employees.map((emp) => (
                <TableRow key={emp.employee_id}>
                  <TableCell>
                    {emp.first_name} {emp.last_name}
                  </TableCell>
                  <TableCell className="text-right">{emp.cp_n1_remaining.toFixed(1)}</TableCell>
                  <TableCell className="text-right">{emp.cp_n_remaining.toFixed(1)}</TableCell>
                  <TableCell className="text-right font-medium">
                    {emp.cp_total_remaining.toFixed(1)}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {(emp.cp_seniority_days ?? 0).toFixed(1)}
                  </TableCell>
                  <TableCell className="text-right">{emp.rtt_remaining.toFixed(1)}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setAdjustTarget(emp)}
                    >
                      Ajuster
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      {adjustTarget ? (
        <AdjustmentDialog
          employee={adjustTarget}
          year={year}
          open={!!adjustTarget}
          onOpenChange={(v) => !v && setAdjustTarget(null)}
        />
      ) : null}
    </Card>
  );
}
