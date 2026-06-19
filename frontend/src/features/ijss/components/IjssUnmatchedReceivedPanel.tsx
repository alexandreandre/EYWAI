import { useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  IJSS_LINE_STATUS_LABELS,
  matchIjssReceivedLine,
  type IjssDashboardRow,
  type IjssUnmatchedReceivedLine,
} from '@/api/ijssTracking';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useToast } from '@/hooks/use-toast';
import { Link2 } from 'lucide-react';

function eur(n: number) {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(n);
}

function sourceLabel(source: string) {
  if (source === 'cpam_decompte') return 'Décompte CPAM';
  if (source === 'bank_transfer') return 'Virement banque';
  return source;
}

interface IjssUnmatchedReceivedPanelProps {
  lines: IjssUnmatchedReceivedLine[];
  dashboardRows: IjssDashboardRow[];
  periodClosed: boolean;
  onMatched: () => void;
}

export function IjssUnmatchedReceivedPanel({
  lines,
  dashboardRows,
  periodClosed,
  onMatched,
}: IjssUnmatchedReceivedPanelProps) {
  const { toast } = useToast();
  const [selectedLine, setSelectedLine] = useState<IjssUnmatchedReceivedLine | null>(null);
  const [employeeId, setEmployeeId] = useState('');
  const [expectedLineId, setExpectedLineId] = useState('');

  const employeeOptions = useMemo(
    () =>
      dashboardRows.map((row) => ({
        id: row.employee_id,
        name: row.employee_name,
        expectedLineId: row.expected_line_id ?? '',
      })),
    [dashboardRows],
  );

  const expectedOptions = useMemo(
    () =>
      dashboardRows.filter(
        (row) => !employeeId || row.employee_id === employeeId,
      ),
    [dashboardRows, employeeId],
  );

  const matchMut = useMutation({
    mutationFn: () =>
      matchIjssReceivedLine(
        selectedLine!.id,
        employeeId,
        expectedLineId || undefined,
      ),
    onSuccess: () => {
      toast({ title: 'Ligne rapprochée manuellement' });
      setSelectedLine(null);
      setEmployeeId('');
      setExpectedLineId('');
      onMatched();
    },
    onError: (e: Error) => toast({ variant: 'destructive', title: e.message }),
  });

  if (lines.length === 0) return null;

  return (
    <>
      <Card className="border-amber-500/30">
        <CardHeader>
          <CardTitle className="text-base">
            Lignes import non rapprochées
            <Badge variant="secondary" className="ml-2">
              {lines.length}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>Libellé import</TableHead>
                <TableHead>NIR</TableHead>
                <TableHead className="text-right">Montant</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {lines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell>{sourceLabel(line.source)}</TableCell>
                  <TableCell className="max-w-[200px] truncate">
                    {line.employee_name_raw || '—'}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {line.employee_nir || '—'}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{eur(line.amount)}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={periodClosed}
                      onClick={() => {
                        setSelectedLine(line);
                        setEmployeeId('');
                        setExpectedLineId('');
                      }}
                    >
                      <Link2 className="mr-2 h-4 w-4" />
                      Rapprocher
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={Boolean(selectedLine)} onOpenChange={(o) => !o && setSelectedLine(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rapprochement manuel</DialogTitle>
            <DialogDescription>
              Associez la ligne importée (
              {selectedLine ? eur(selectedLine.amount) : ''}) à un salarié du mois.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <p className="text-sm font-medium">Salarié</p>
              <Select
                value={employeeId}
                onValueChange={(v) => {
                  setEmployeeId(v);
                  const row = employeeOptions.find((o) => o.id === v);
                  setExpectedLineId(row?.expectedLineId ?? '');
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Choisir un salarié" />
                </SelectTrigger>
                <SelectContent>
                  {employeeOptions.map((opt) => (
                    <SelectItem key={opt.id} value={opt.id}>
                      {opt.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {expectedOptions.some((r) => r.expected_line_id) && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Ligne attendue IJSS (optionnel)</p>
                <Select value={expectedLineId} onValueChange={setExpectedLineId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Ligne attendue du mois" />
                  </SelectTrigger>
                  <SelectContent>
                    {expectedOptions
                      .filter((r) => r.expected_line_id)
                      .map((r) => (
                        <SelectItem key={r.expected_line_id!} value={r.expected_line_id!}>
                          {r.employee_name} —{' '}
                          {IJSS_LINE_STATUS_LABELS[r.line_status] ?? r.line_status}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedLine(null)}>
              Annuler
            </Button>
            <Button
              disabled={!employeeId || matchMut.isPending}
              onClick={() => matchMut.mutate()}
            >
              Enregistrer le rapprochement
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
