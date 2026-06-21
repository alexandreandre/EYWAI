import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarRange, Plus, Trash2 } from 'lucide-react';
import {
  createWorkTimePeriod,
  deleteWorkTimePeriod,
  listWorkTimePeriods,
  updateWorkTimePeriod,
  type WorkTimePeriod,
} from '@/api/modulation';
import { useAuth } from '@/contexts/AuthContext';
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
import { Switch } from '@/components/ui/switch';
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

const EMPTY: WorkTimePeriod = {
  label: '',
  start_date: new Date().toISOString().slice(0, 10),
  end_date: null,
  daily_reference_hours: null,
  weekly_reference_hours: null,
  affects_payroll: true,
  affects_planning: false,
  is_active: true,
};

export default function WorkTimePeriodsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const canEdit = ['admin', 'rh', 'collaborateur_rh'].includes(user?.role ?? '');

  const { data: periods = [], isLoading } = useQuery({
    queryKey: queryKeys.workTimePeriods(companyId),
    queryFn: listWorkTimePeriods,
    enabled: Boolean(companyId),
  });

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<WorkTimePeriod | null>(null);
  const [form, setForm] = useState<WorkTimePeriod>(EMPTY);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.workTimePeriods(companyId) });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (editing?.id) {
        return updateWorkTimePeriod(editing.id, form);
      }
      return createWorkTimePeriod(form);
    },
    onSuccess: () => {
      toast({ title: 'Période enregistrée' });
      setDialogOpen(false);
      invalidate();
    },
    onError: (err: Error) => {
      toast({ title: 'Erreur', description: err.message, variant: 'destructive' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteWorkTimePeriod(id),
    onSuccess: () => {
      toast({ title: 'Période désactivée' });
      invalidate();
    },
  });

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY);
    setDialogOpen(true);
  };

  const openEdit = (p: WorkTimePeriod) => {
    setEditing(p);
    setForm(p);
    setDialogOpen(true);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarRange className="h-5 w-5" />
          Périodes de référence horaire
        </CardTitle>
        <CardDescription>
          Activité réduite, horaire transitoire ou bascule temporaire — indépendant de l&apos;accord de modulation.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {canEdit && (
          <Button type="button" size="sm" variant="secondary" onClick={openCreate}>
            <Plus className="mr-1 h-4 w-4" />
            Ajouter une période
          </Button>
        )}
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : periods.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune période configurée.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Libellé</TableHead>
                <TableHead>Dates</TableHead>
                <TableHead>Référence</TableHead>
                <TableHead>Paie</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {periods.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{p.label}</TableCell>
                  <TableCell className="text-sm">
                    {p.start_date}
                    {p.end_date ? ` → ${p.end_date}` : ' → …'}
                  </TableCell>
                  <TableCell className="text-sm">
                    {p.daily_reference_hours != null
                      ? `${p.daily_reference_hours} h/j`
                      : p.weekly_reference_hours != null
                        ? `${p.weekly_reference_hours} h/sem.`
                        : '—'}
                  </TableCell>
                  <TableCell>{p.affects_payroll ? 'Oui' : 'Non'}</TableCell>
                  <TableCell className="text-right">
                    {canEdit && (
                      <>
                        <Button size="sm" variant="ghost" onClick={() => openEdit(p)}>
                          Modifier
                        </Button>
                        {p.is_active && p.id && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => deleteMutation.mutate(p.id!)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editing ? 'Modifier la période' : 'Nouvelle période de référence'}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label>Libellé</Label>
                <Input
                  value={form.label}
                  onChange={(e) => setForm({ ...form, label: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Début</Label>
                  <Input
                    type="date"
                    value={form.start_date}
                    onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Fin (optionnel)</Label>
                  <Input
                    type="date"
                    value={form.end_date ?? ''}
                    onChange={(e) =>
                      setForm({ ...form, end_date: e.target.value || null })
                    }
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Heures / jour</Label>
                  <Input
                    type="number"
                    step={0.25}
                    value={form.daily_reference_hours ?? ''}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        daily_reference_hours:
                          e.target.value === '' ? null : Number(e.target.value),
                      })
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label>Heures / semaine</Label>
                  <Input
                    type="number"
                    step={0.5}
                    value={form.weekly_reference_hours ?? ''}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        weekly_reference_hours:
                          e.target.value === '' ? null : Number(e.target.value),
                      })
                    }
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={form.affects_payroll}
                  onCheckedChange={(v) => setForm({ ...form, affects_payroll: v })}
                />
                <Label>Impacte le calcul paie (HS / écarts)</Label>
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setDialogOpen(false)}>
                Annuler
              </Button>
              <Button
                disabled={saveMutation.isPending || !form.label}
                onClick={() => saveMutation.mutate()}
              >
                Enregistrer
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
