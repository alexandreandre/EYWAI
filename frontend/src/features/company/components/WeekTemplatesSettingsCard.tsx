import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { LayoutTemplate, Plus, Trash2 } from 'lucide-react';
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
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';

const DEFAULT_DAYS = [1, 2, 3, 4, 5].map((day) => ({
  day,
  hours: 7,
  type: 'travail',
}));

const EMPTY: WeekScheduleTemplate = {
  name: '',
  weekly_hours: 35,
  day_configs: DEFAULT_DAYS,
  modulation_tier: 'neutral',
  is_active: true,
  description: '',
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
  const [editing, setEditing] = useState<WeekScheduleTemplate | null>(null);
  const [form, setForm] = useState<WeekScheduleTemplate>(EMPTY);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.weekTemplates(companyId) });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (editing?.id) {
        return updateWeekTemplate(editing.id, form);
      }
      return createWeekTemplate(form);
    },
    onSuccess: () => {
      toast({ title: 'Modèle enregistré' });
      setDialogOpen(false);
      invalidate();
    },
    onError: () => {
      toast({ title: 'Erreur', description: 'Enregistrement impossible.', variant: 'destructive' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteWeekTemplate(id),
    onSuccess: () => {
      toast({ title: 'Modèle supprimé' });
      invalidate();
    },
  });

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY);
    setDialogOpen(true);
  };

  const openEdit = (t: WeekScheduleTemplate) => {
    setEditing(t);
    setForm(t);
    setDialogOpen(true);
  };

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
          Horaires de référence réutilisables pour le planning et les calendriers.
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
                        <Button
                          size="sm"
                          variant="ghost"
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
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editing ? 'Modifier le modèle' : 'Nouveau modèle de semaine'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label>Nom</Label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Heures hebdomadaires</Label>
                  <Input
                    type="number"
                    step={0.25}
                    value={form.weekly_hours}
                    onChange={(e) =>
                      setForm({ ...form, weekly_hours: Number(e.target.value) || 35 })
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label>Type de semaine</Label>
                  <Select
                    value={form.modulation_tier}
                    onValueChange={(v: 'high' | 'low' | 'neutral') =>
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
              <div className="space-y-1">
                <Label>Heures / jour (lun–ven)</Label>
                <Input
                  type="number"
                  step={0.25}
                  value={
                    (form.day_configs[0] as { hours?: number })?.hours ?? 7
                  }
                  onChange={(e) => {
                    const h = Number(e.target.value) || 0;
                    setForm({
                      ...form,
                      day_configs: [1, 2, 3, 4, 5].map((day) => ({
                        day,
                        hours: h,
                        type: 'travail',
                      })),
                      weekly_hours: h * 5,
                    });
                  }}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setDialogOpen(false)}>
                Annuler
              </Button>
              <Button
                disabled={saveMutation.isPending || !form.name}
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
