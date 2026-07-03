/**
 * Dialogue de création / édition d'un plan de calendrier horaire.
 *
 * Permet aux RH de configurer sans code : portée (société / équipe / salariés),
 * cycle de modèles (alternance semaine A/B/…N), période, mode d'écrasement.
 */
import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDown, ArrowUp, X } from 'lucide-react';
import { listWeekTemplates, type WeekScheduleTemplate } from '@/api/modulation';
import { getTeams } from '@/api/teams';
import { getEmployeesLite } from '@/api/employees';
import {
  createSchedulePlan,
  updateSchedulePlan,
  type OverwriteMode,
  type ScopeType,
  type SchedulePlan,
  type SchedulePlanUpsert,
} from '@/api/schedulePlans';
import { Button } from '@/components/ui/button';
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
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companyId: string;
  /** Plan existant à éditer, ou pré-rempli pour duplication (sans id). */
  plan: SchedulePlan | null;
  duplicate?: boolean;
};

type FormState = {
  name: string;
  scope_type: ScopeType;
  team_id: string;
  employee_ids: string[];
  template_cycle: string[];
  cycle_anchor: string;
  start_date: string;
  end_date: string;
  overwrite_mode: OverwriteMode;
  needs_confirmation: boolean;
  notes: string;
};

function planToForm(plan: SchedulePlan | null): FormState {
  const ref = (plan?.scope_ref ?? {}) as { team_id?: string; employee_ids?: string[] };
  return {
    name: plan?.name ?? '',
    scope_type: plan?.scope_type ?? 'company',
    team_id: ref.team_id ?? '',
    employee_ids: ref.employee_ids ?? [],
    template_cycle: plan?.template_cycle ?? [],
    cycle_anchor: plan?.cycle_anchor ?? '',
    start_date: plan?.start_date ?? `${new Date().getFullYear()}-01-01`,
    end_date: plan?.end_date ?? `${new Date().getFullYear()}-12-31`,
    overwrite_mode: plan?.overwrite_mode ?? 'preserve_manual',
    needs_confirmation: plan?.needs_confirmation ?? false,
    notes: plan?.notes ?? '',
  };
}

export function SchedulePlanDialog({ open, onOpenChange, companyId, plan, duplicate }: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(planToForm(plan));
  const [empSearch, setEmpSearch] = useState('');

  useEffect(() => {
    if (open) {
      setForm(planToForm(plan));
      setEmpSearch('');
    }
  }, [open, plan]);

  const templatesQuery = useQuery({
    queryKey: ['week-templates-for-plan', companyId],
    queryFn: listWeekTemplates,
    enabled: open,
  });
  const teamsQuery = useQuery({
    queryKey: ['teams-for-plan', companyId],
    queryFn: () => getTeams(false),
    enabled: open && form.scope_type === 'team',
  });
  const employeesQuery = useQuery({
    queryKey: ['employees-for-plan', companyId],
    queryFn: getEmployeesLite,
    enabled: open && form.scope_type === 'employees',
  });

  const templates: WeekScheduleTemplate[] = templatesQuery.data ?? [];
  const templateName = (id: string) => templates.find((t) => t.id === id)?.name ?? id;

  const editingExisting = Boolean(plan?.id) && !duplicate;

  const saveMutation = useMutation({
    mutationFn: async () => {
      const scope_ref: Record<string, unknown> =
        form.scope_type === 'team'
          ? { team_id: form.team_id }
          : form.scope_type === 'employees'
            ? { employee_ids: form.employee_ids }
            : {};
      const payload: SchedulePlanUpsert = {
        name: form.name,
        scope_type: form.scope_type,
        scope_ref,
        template_cycle: form.template_cycle,
        cycle_anchor: form.cycle_anchor || null,
        start_date: form.start_date,
        end_date: form.end_date || null,
        overwrite_mode: form.overwrite_mode,
        needs_confirmation: form.needs_confirmation,
        notes: form.notes || null,
        is_active: true,
      };
      return editingExisting ? updateSchedulePlan(plan!.id, payload) : createSchedulePlan(payload);
    },
    onSuccess: () => {
      toast({ title: editingExisting ? 'Plan mis à jour' : 'Plan créé' });
      queryClient.invalidateQueries({ queryKey: ['schedule-plans', companyId] });
      onOpenChange(false);
    },
    onError: (e: unknown) =>
      toast({
        title: 'Échec',
        description: e instanceof Error ? e.message : 'Enregistrement impossible.',
        variant: 'destructive',
      }),
  });

  const addTemplate = (id: string) =>
    setForm((f) => ({ ...f, template_cycle: [...f.template_cycle, id] }));
  const removeTemplateAt = (idx: number) =>
    setForm((f) => ({ ...f, template_cycle: f.template_cycle.filter((_, i) => i !== idx) }));
  const moveTemplate = (idx: number, dir: -1 | 1) =>
    setForm((f) => {
      const next = [...f.template_cycle];
      const j = idx + dir;
      if (j < 0 || j >= next.length) return f;
      [next[idx], next[j]] = [next[j], next[idx]];
      return { ...f, template_cycle: next };
    });

  const toggleEmployee = (id: string) =>
    setForm((f) => ({
      ...f,
      employee_ids: f.employee_ids.includes(id)
        ? f.employee_ids.filter((e) => e !== id)
        : [...f.employee_ids, id],
    }));

  const filteredEmployees = useMemo(() => {
    const rows = employeesQuery.data ?? [];
    const q = empSearch.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((e) => `${e.first_name} ${e.last_name}`.toLowerCase().includes(q));
  }, [employeesQuery.data, empSearch]);

  const isCycle = form.template_cycle.length > 1;
  const canSave =
    Boolean(form.name) &&
    form.template_cycle.length >= 1 &&
    (form.scope_type !== 'team' || Boolean(form.team_id)) &&
    (form.scope_type !== 'employees' || form.employee_ids.length > 0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editingExisting ? 'Modifier le plan' : 'Nouveau plan de calendrier'}</DialogTitle>
        </DialogHeader>

        <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
          <div className="space-y-1">
            <Label>Nom du plan</Label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>

          {/* Portée */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>Portée</Label>
              <Select
                value={form.scope_type}
                onValueChange={(v: ScopeType) => setForm({ ...form, scope_type: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="company">Toute la société</SelectItem>
                  <SelectItem value="team">Une équipe</SelectItem>
                  <SelectItem value="employees">Salariés sélectionnés</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.scope_type === 'team' && (
              <div className="space-y-1">
                <Label>Équipe</Label>
                <Select value={form.team_id} onValueChange={(v) => setForm({ ...form, team_id: v })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choisir…" />
                  </SelectTrigger>
                  <SelectContent>
                    {(teamsQuery.data?.teams ?? []).map((t) => (
                      <SelectItem key={t.id} value={t.id}>
                        {t.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>

          {form.scope_type === 'employees' && (
            <div className="space-y-1">
              <Label>Salariés ({form.employee_ids.length} sélectionné(s))</Label>
              <Input
                placeholder="Rechercher…"
                value={empSearch}
                onChange={(e) => setEmpSearch(e.target.value)}
              />
              <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border p-2">
                {filteredEmployees.map((e) => (
                  <label key={e.id} className="flex cursor-pointer items-center gap-2 text-sm">
                    <Checkbox
                      checked={form.employee_ids.includes(e.id)}
                      onCheckedChange={() => toggleEmployee(e.id)}
                    />
                    {e.first_name} {e.last_name}
                  </label>
                ))}
                {filteredEmployees.length === 0 && (
                  <p className="text-xs text-muted-foreground">Aucun salarié.</p>
                )}
              </div>
            </div>
          )}

          {/* Cycle de modèles (alternance) */}
          <div className="space-y-1">
            <Label>Modèle(s) — cycle d'alternance</Label>
            <Select value="" onValueChange={(v) => v && addTemplate(v)}>
              <SelectTrigger>
                <SelectValue placeholder="Ajouter un modèle au cycle…" />
              </SelectTrigger>
              <SelectContent>
                {templates.map((t) => (
                  <SelectItem key={t.id} value={t.id!}>
                    {t.name} · {t.weekly_hours}h
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {form.template_cycle.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Ajoutez un modèle. Plusieurs modèles = alternance (semaine A, B, …).
              </p>
            ) : (
              <ul className="space-y-1">
                {form.template_cycle.map((id, idx) => (
                  <li
                    key={`${id}-${idx}`}
                    className="flex items-center justify-between gap-2 rounded-md border px-2 py-1 text-sm"
                  >
                    <span className="truncate">
                      <span className="mr-2 font-mono text-xs text-muted-foreground">
                        S{String.fromCharCode(65 + idx)}
                      </span>
                      {templateName(id)}
                    </span>
                    <span className="flex shrink-0 gap-1">
                      <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => moveTemplate(idx, -1)}>
                        <ArrowUp className="h-3 w-3" />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => moveTemplate(idx, 1)}>
                        <ArrowDown className="h-3 w-3" />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => removeTemplateAt(idx)}>
                        <X className="h-3 w-3" />
                      </Button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {isCycle && (
            <div className="space-y-1">
              <Label>Ancrage de l'alternance (lundi de la semaine A)</Label>
              <Input
                type="date"
                value={form.cycle_anchor}
                onChange={(e) => setForm({ ...form, cycle_anchor: e.target.value })}
              />
            </div>
          )}

          {/* Période */}
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
              <Label>Fin (vide = ouvert)</Label>
              <Input
                type="date"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label>Mode de génération</Label>
            <Select
              value={form.overwrite_mode}
              onValueChange={(v: OverwriteMode) => setForm({ ...form, overwrite_mode: v })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="preserve_manual">Conserver les jours modifiés à la main</SelectItem>
                <SelectItem value="fill_empty">Ne remplir que les jours vides</SelectItem>
                <SelectItem value="overwrite_all">Écraser tout</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label>Notes RH</Label>
            <Textarea
              rows={2}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button disabled={!canSave || saveMutation.isPending} onClick={() => saveMutation.mutate()}>
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
