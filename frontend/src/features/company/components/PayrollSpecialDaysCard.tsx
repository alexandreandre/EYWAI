import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarClock, Trash2 } from 'lucide-react';
import {
  createSpecialPayrollDay,
  deleteSpecialPayrollDay,
  listSpecialPayrollDays,
  type SpecialPayrollDay,
} from '@/api/payrollVariables';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { queryKeys } from '@/lib/queryKeys';

const KIND_LABELS: Record<SpecialPayrollDay['kind'], string> = {
  bridge: 'Pont (prime astreinte)',
  christmas_week: 'Semaine de Noël (override)',
};

export default function PayrollSpecialDaysCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const year = new Date().getFullYear();

  const canEdit =
    user?.role === 'admin' || user?.role === 'rh' || user?.role === 'collaborateur_rh';

  const [draft, setDraft] = useState<SpecialPayrollDay>({
    day_date: '',
    kind: 'bridge',
    label: '',
  });

  const { data: days = [], isLoading } = useQuery({
    queryKey: queryKeys.payrollSpecialDays(activeCompanyId, year),
    queryFn: () => listSpecialPayrollDays(year),
    enabled: Boolean(activeCompanyId),
  });

  const createDay = useMutation({
    mutationFn: () => createSpecialPayrollDay(draft),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.payrollSpecialDays(activeCompanyId, year),
      });
      toast({ title: 'Jour enregistré' });
      setDraft({ day_date: '', kind: 'bridge', label: '' });
    },
  });

  const removeDay = useMutation({
    mutationFn: (id: string) => deleteSpecialPayrollDay(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.payrollSpecialDays(activeCompanyId, year),
      });
      toast({ title: 'Jour supprimé' });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarClock className="h-5 w-5" />
          Jours spéciaux paie (ponts / Noël)
        </CardTitle>
        <CardDescription>
          Dates utilisées par les règles astreinte (prime pont 250 €, semaine Noël).
          Distinct des jours fériés légaux.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Libellé</TableHead>
                {canEdit && <TableHead className="w-12" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {days.map((d) => (
                <TableRow key={d.id}>
                  <TableCell>{d.day_date}</TableCell>
                  <TableCell>{KIND_LABELS[d.kind] ?? d.kind}</TableCell>
                  <TableCell>{d.label ?? '—'}</TableCell>
                  {canEdit && d.id && (
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Supprimer"
                        onClick={() => removeDay.mutate(d.id!)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
              {days.length === 0 && (
                <TableRow>
                  <TableCell colSpan={canEdit ? 4 : 3} className="text-muted-foreground">
                    Aucun jour spécial pour {year}.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}

        {canEdit && (
          <div className="grid gap-3 rounded-lg border p-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>Date</Label>
              <Input
                type="date"
                value={draft.day_date}
                onChange={(e) => setDraft({ ...draft, day_date: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Type</Label>
              <Select
                value={draft.kind}
                onValueChange={(v) =>
                  setDraft({ ...draft, kind: v as SpecialPayrollDay['kind'] })
                }
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(KIND_LABELS).map(([k, label]) => (
                    <SelectItem key={k} value={k}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Libellé (optionnel)</Label>
              <Input
                value={draft.label ?? ''}
                onChange={(e) => setDraft({ ...draft, label: e.target.value })}
                placeholder="Pont Ascension"
              />
            </div>
            <div className="sm:col-span-3">
              <Button
                variant="outline"
                disabled={!draft.day_date || createDay.isPending}
                onClick={() => createDay.mutate()}
              >
                Ajouter
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
