import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, LayoutTemplate, Plus, Trash2 } from 'lucide-react';
import {
  createWeekTemplate,
  deleteWeekTemplate,
  listWeekTemplates,
  updateWeekTemplate,
  type WeekScheduleTemplate,
} from '@/api/modulation';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
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
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';

// ─── Modèle d'édition jour par jour (lundi=1 … dimanche=7) ──────────────

const DAY_LABELS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'];

type EditDay = {
  day: number;
  worked: boolean;
  hours: number;
  start: string;
  end: string;
  break_minutes: number;
  break_paid: boolean;
  comment: string;
};

type RawDay = {
  day?: number;
  type?: string;
  hours?: number;
  start?: string | null;
  end?: string | null;
  break_minutes?: number;
  break_paid?: boolean;
  comment?: string | null;
};

function buildEditDays(dayConfigs: Record<string, unknown>[]): EditDay[] {
  const byDay = new Map<number, RawDay>();
  for (const raw of (dayConfigs ?? []) as RawDay[]) {
    if (raw && typeof raw.day === 'number') byDay.set(raw.day, raw);
  }
  return [1, 2, 3, 4, 5, 6, 7].map((day) => {
    const r = byDay.get(day);
    const worked = Boolean(r) && (r?.type ?? 'travail') === 'travail';
    return {
      day,
      worked,
      hours: r?.hours ?? (day <= 5 ? 7 : 0),
      start: r?.start ?? '',
      end: r?.end ?? '',
      break_minutes: r?.break_minutes ?? 0,
      break_paid: Boolean(r?.break_paid),
      comment: r?.comment ?? '',
    };
  });
}

function serializeDays(days: EditDay[]): Record<string, unknown>[] {
  return days
    .filter((d) => d.worked)
    .map((d) => ({
      day: d.day,
      type: 'travail',
      hours: Number(d.hours) || 0,
      start: d.start || null,
      end: d.end || null,
      break_minutes: Number(d.break_minutes) || 0,
      break_paid: d.break_paid,
      comment: d.comment || null,
    }));
}

function weeklyTotal(days: EditDay[]): number {
  const total = days.reduce((s, d) => (d.worked ? s + (Number(d.hours) || 0) : s), 0);
  return Math.round(total * 100) / 100;
}

type FormState = {
  id?: string;
  name: string;
  description: string;
  modulation_tier: 'high' | 'low' | 'neutral';
  days: EditDay[];
};

const EMPTY_FORM: FormState = {
  name: '',
  description: '',
  modulation_tier: 'neutral',
  days: buildEditDays([1, 2, 3, 4, 5].map((day) => ({ day, hours: 7, type: 'travail' }))),
};

export default function WeekTemplatesSettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const canEdit = ['admin', 'rh', 'collaborateur_rh'].includes(user?.role ?? '');

  const { data: templates = [], isLoading } = useQuery({
    queryKey: queryKeys.weekTemplates(companyId),
    queryFn: listWeekTemplates,
    enabled: Boolean(companyId),
  });

  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.weekTemplates(companyId) });

  const buildPayload = (f: FormState): WeekScheduleTemplate => ({
    name: f.name,
    description: f.description,
    modulation_tier: f.modulation_tier,
    weekly_hours: weeklyTotal(f.days),
    day_configs: serializeDays(f.days),
    is_active: true,
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = buildPayload(form);
      return form.id ? updateWeekTemplate(form.id, payload) : createWeekTemplate(payload);
    },
    onSuccess: () => {
      toast({ title: 'Modèle enregistré' });
      setDialogOpen(false);
      invalidate();
    },
    onError: () =>
      toast({ title: 'Erreur', description: 'Enregistrement impossible.', variant: 'destructive' }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteWeekTemplate(id),
    onSuccess: () => {
      toast({ title: 'Modèle supprimé' });
      invalidate();
    },
  });

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };

  const openEdit = (t: WeekScheduleTemplate) => {
    setForm({
      id: t.id,
      name: t.name,
      description: t.description ?? '',
      modulation_tier: (t.modulation_tier as FormState['modulation_tier']) ?? 'neutral',
      days: buildEditDays(t.day_configs ?? []),
    });
    setDialogOpen(true);
  };

  const openDuplicate = (t: WeekScheduleTemplate) => {
    setForm({
      name: `${t.name} (copie)`,
      description: t.description ?? '',
      modulation_tier: (t.modulation_tier as FormState['modulation_tier']) ?? 'neutral',
      days: buildEditDays(t.day_configs ?? []),
    });
    setDialogOpen(true);
  };

  const total = useMemo(() => weeklyTotal(form.days), [form.days]);

  const setDay = (idx: number, patch: Partial<EditDay>) =>
    setForm((f) => ({
      ...f,
      days: f.days.map((d, i) => (i === idx ? { ...d, ...patch } : d)),
    }));

  const tierLabel = (tier: string) =>
    tier === 'high' ? 'Haute' : tier === 'low' ? 'Basse' : 'Neutre';

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <LayoutTemplate className="h-5 w-5" />
          Modèles de semaine
        </CardTitle>
        <CardDescription>
          Horaires de référence réutilisables : configurez chaque jour (heures, horaires, pause),
          le total hebdomadaire est calculé automatiquement.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {canEdit && (
          <Button type="button" size="sm" variant="secondary" onClick={openCreate}>
            <Plus className="mr-1 h-4 w-4" />
            Nouveau modèle
          </Button>
        )}
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : templates.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun modèle enregistré.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nom</TableHead>
                <TableHead>Heures / sem.</TableHead>
                <TableHead>Cycle</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {templates.map((t) => (
                <TableRow key={t.id}>
                  <TableCell>{t.name}</TableCell>
                  <TableCell>{t.weekly_hours} h</TableCell>
                  <TableCell>{tierLabel(t.modulation_tier)}</TableCell>
                  <TableCell className="text-right">
                    {canEdit && t.id && (
                      <>
                        <Button size="sm" variant="ghost" onClick={() => openEdit(t)}>
                          Modifier
                        </Button>
                        <Button size="sm" variant="ghost" title="Dupliquer" onClick={() => openDuplicate(t)}>
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          title="Supprimer"
                          onClick={() => deleteMutation.mutate(t.id!)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="max-w-3xl">
            <DialogHeader>
              <DialogTitle>{form.id ? 'Modifier le modèle' : 'Nouveau modèle de semaine'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="space-y-1 sm:col-span-2">
                  <Label>Nom</Label>
                  <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                </div>
                <div className="space-y-1">
                  <Label>Type de semaine</Label>
                  <Select
                    value={form.modulation_tier}
                    onValueChange={(v: FormState['modulation_tier']) =>
                      setForm({ ...form, modulation_tier: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="high">Haute</SelectItem>
                      <SelectItem value="low">Basse</SelectItem>
                      <SelectItem value="neutral">Neutre</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="overflow-x-auto rounded-md border">
                <table className="w-full min-w-[640px] text-sm">
                  <thead className="bg-muted/40 text-xs">
                    <tr>
                      <th className="px-2 py-1 text-left">Jour</th>
                      <th className="px-2 py-1">Travaillé</th>
                      <th className="px-2 py-1">Heures</th>
                      <th className="px-2 py-1">Début</th>
                      <th className="px-2 py-1">Fin</th>
                      <th className="px-2 py-1">Pause (min)</th>
                      <th className="px-2 py-1">Payée</th>
                    </tr>
                  </thead>
                  <tbody>
                    {form.days.map((d, idx) => (
                      <tr key={d.day} className={d.worked ? '' : 'opacity-50'}>
                        <td className="px-2 py-1 font-medium">{DAY_LABELS[d.day - 1]}</td>
                        <td className="px-2 py-1 text-center">
                          <Checkbox
                            checked={d.worked}
                            onCheckedChange={(v) => setDay(idx, { worked: Boolean(v) })}
                          />
                        </td>
                        <td className="px-2 py-1">
                          <Input
                            type="number"
                            step={0.05}
                            className="h-8 w-20"
                            disabled={!d.worked}
                            value={d.hours}
                            onChange={(e) => setDay(idx, { hours: Number(e.target.value) || 0 })}
                          />
                        </td>
                        <td className="px-2 py-1">
                          <Input
                            type="time"
                            className="h-8 w-28"
                            disabled={!d.worked}
                            value={d.start}
                            onChange={(e) => setDay(idx, { start: e.target.value })}
                          />
                        </td>
                        <td className="px-2 py-1">
                          <Input
                            type="time"
                            className="h-8 w-28"
                            disabled={!d.worked}
                            value={d.end}
                            onChange={(e) => setDay(idx, { end: e.target.value })}
                          />
                        </td>
                        <td className="px-2 py-1">
                          <Input
                            type="number"
                            className="h-8 w-20"
                            disabled={!d.worked}
                            value={d.break_minutes}
                            onChange={(e) => setDay(idx, { break_minutes: Number(e.target.value) || 0 })}
                          />
                        </td>
                        <td className="px-2 py-1 text-center">
                          <Checkbox
                            checked={d.break_paid}
                            disabled={!d.worked}
                            onCheckedChange={(v) => setDay(idx, { break_paid: Boolean(v) })}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label>Commentaire RH</Label>
                  <Textarea
                    rows={2}
                    className="w-80"
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                  />
                </div>
                <div className="text-right">
                  <div className="text-xs text-muted-foreground">Total hebdomadaire</div>
                  <div className="text-2xl font-semibold">{total} h</div>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setDialogOpen(false)}>
                Annuler
              </Button>
              <Button disabled={saveMutation.isPending || !form.name} onClick={() => saveMutation.mutate()}>
                Enregistrer
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
