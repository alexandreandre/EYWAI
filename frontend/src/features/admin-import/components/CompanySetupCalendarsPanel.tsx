/**
 * Étape « Calendriers horaires 2026 » du parcours guidé.
 *
 * Permet aux RH de : consulter la bibliothèque de presets (modèles + plans
 * éditables), appliquer un preset société, puis prévisualiser (dry-run) et
 * générer l'année 2026 dans les calendriers réellement utilisés par la paie
 * (employee_schedules.planned_calendar.calendrier_prevu).
 */
import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarRange, Copy, Loader2, Pencil, Plus, Power, Sparkles, Trash2, Wand2 } from 'lucide-react';
import {
  applySchedulePreset,
  deleteSchedulePlan,
  generateAllSchedulePlans,
  generateSchedulePlan,
  listSchedulePlans,
  listSchedulePresets,
  updateSchedulePlan,
  type GenerationBatchResult,
  type GenerationResult,
  type Preset,
  type SchedulePlan,
  type SchedulePlanUpsert,
} from '@/api/schedulePlans';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { SchedulePlanDialog } from '@/features/admin-import/components/SchedulePlanDialog';

function planToUpsert(plan: SchedulePlan, patch: Partial<SchedulePlanUpsert> = {}): SchedulePlanUpsert {
  return {
    name: plan.name,
    scope_type: plan.scope_type,
    scope_ref: plan.scope_ref,
    template_cycle: plan.template_cycle,
    cycle_anchor: plan.cycle_anchor ?? null,
    start_date: plan.start_date,
    end_date: plan.end_date ?? null,
    overwrite_mode: plan.overwrite_mode,
    needs_confirmation: plan.needs_confirmation,
    notes: plan.notes ?? null,
    is_active: plan.is_active,
    ...patch,
  };
}

const GENERATION_YEAR = 2026;

const SCOPE_LABELS: Record<string, string> = {
  company: 'Toute la société',
  team: 'Équipe',
  service: 'Service',
  employees: 'Salariés sélectionnés',
};

type Props = {
  companyId: string;
};

export function CompanySetupCalendarsPanel({ companyId }: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selectedPreset, setSelectedPreset] = useState<string>('');
  const [preview, setPreview] = useState<GenerationResult | null>(null);
  const [activePlanId, setActivePlanId] = useState<string | null>(null);
  const [planDialogOpen, setPlanDialogOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState<SchedulePlan | null>(null);
  const [duplicating, setDuplicating] = useState(false);
  const [batchResult, setBatchResult] = useState<GenerationBatchResult | null>(null);

  const presetsQuery = useQuery({
    queryKey: ['schedule-presets', companyId],
    queryFn: listSchedulePresets,
    enabled: Boolean(companyId),
  });

  const plansQuery = useQuery({
    queryKey: ['schedule-plans', companyId],
    queryFn: listSchedulePlans,
    enabled: Boolean(companyId),
  });

  const applyMutation = useMutation({
    mutationFn: (presetKey: string) => applySchedulePreset(presetKey),
    onSuccess: (res, presetKey) => {
      const extra =
        presetKey === 'mbc'
          ? ' Étape 2 : appliquez le preset pointage « 3×8 industriel » (Temps de travail → Pointages).'
          : '';
      toast({
        title: 'Preset appliqué',
        description: `${res.templates_created} modèle(s) et ${res.plans_created} plan(s) créés.${extra}`,
      });
      queryClient.invalidateQueries({ queryKey: ['schedule-plans', companyId] });
    },
    onError: (e: unknown) =>
      toast({
        title: 'Échec',
        description: e instanceof Error ? e.message : 'Erreur lors de l’application du preset.',
        variant: 'destructive',
      }),
  });

  const generateMutation = useMutation({
    mutationFn: (opts: { planId: string; dryRun: boolean }) =>
      generateSchedulePlan({
        plan_id: opts.planId,
        year: GENERATION_YEAR,
        dry_run: opts.dryRun,
      }),
    onSuccess: (res, vars) => {
      setPreview(res);
      setActivePlanId(vars.planId);
      if (res.status === 'skipped') {
        toast({ title: 'Génération ignorée', description: res.reason ?? '' });
      } else if (vars.dryRun) {
        toast({
          title: 'Aperçu généré',
          description: `${res.employee_count ?? 0} salarié(s) concerné(s) — rien n’est encore écrit.`,
        });
      } else {
        toast({
          title: 'Calendriers 2026 générés',
          description: `${res.employee_count ?? 0} salarié(s) mis à jour.`,
        });
        queryClient.invalidateQueries({ queryKey: ['schedule-plans', companyId] });
      }
    },
    onError: (e: unknown) =>
      toast({
        title: 'Échec de génération',
        description: e instanceof Error ? e.message : 'Erreur lors de la génération.',
        variant: 'destructive',
      }),
  });

  const toggleActiveMutation = useMutation({
    mutationFn: (plan: SchedulePlan) =>
      updateSchedulePlan(plan.id, planToUpsert(plan, { is_active: !plan.is_active })),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedule-plans', companyId] });
    },
    onError: (e: unknown) =>
      toast({
        title: 'Échec',
        description: e instanceof Error ? e.message : 'Mise à jour impossible.',
        variant: 'destructive',
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: (planId: string) => deleteSchedulePlan(planId),
    onSuccess: () => {
      toast({ title: 'Plan supprimé' });
      queryClient.invalidateQueries({ queryKey: ['schedule-plans', companyId] });
    },
  });

  const batchMutation = useMutation({
    mutationFn: (dryRun: boolean) =>
      generateAllSchedulePlans({ year: GENERATION_YEAR, dry_run: dryRun }),
    onSuccess: (res, dryRun) => {
      setBatchResult(res);
      if (dryRun) {
        toast({
          title: 'Aperçu société',
          description: `${res.plans_processed} plan(s) · ${res.employee_writes} écriture(s) simulées.`,
        });
      } else {
        toast({
          title: 'Toute la société générée',
          description: `${res.plans_processed} plan(s) appliqués · ${res.employee_writes} calendrier(s) écrits.`,
        });
        queryClient.invalidateQueries({ queryKey: ['schedule-plans', companyId] });
      }
    },
    onError: (e: unknown) =>
      toast({
        title: 'Échec',
        description: e instanceof Error ? e.message : 'Génération société impossible.',
        variant: 'destructive',
      }),
  });

  const openCreatePlan = () => {
    setEditingPlan(null);
    setDuplicating(false);
    setPlanDialogOpen(true);
  };
  const openEditPlan = (plan: SchedulePlan) => {
    setEditingPlan(plan);
    setDuplicating(false);
    setPlanDialogOpen(true);
  };
  const openDuplicatePlan = (plan: SchedulePlan) => {
    setEditingPlan({ ...plan, name: `${plan.name} (copie)` });
    setDuplicating(true);
    setPlanDialogOpen(true);
  };

  const presets = presetsQuery.data ?? [];
  const plans = plansQuery.data ?? [];
  const currentPreset: Preset | undefined = useMemo(
    () => presets.find((p) => p.key === selectedPreset),
    [presets, selectedPreset],
  );

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarRange className="h-5 w-5" />
            Calendriers horaires 2026
          </CardTitle>
          <CardDescription>
            Appliquez un modèle société (presets Elsa / Cartol), ajustez si besoin, puis générez
            l’année 2026. Tous les modèles restent modifiables par les RH.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[220px]">
              <label className="mb-1 block text-sm font-medium">Preset société</label>
              <Select value={selectedPreset} onValueChange={setSelectedPreset}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir une société…" />
                </SelectTrigger>
                <SelectContent>
                  {presets.map((p) => (
                    <SelectItem key={p.key} value={p.key}>
                      {p.company_label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={() => selectedPreset && applyMutation.mutate(selectedPreset)}
              disabled={!selectedPreset || applyMutation.isPending}
            >
              {applyMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="mr-2 h-4 w-4" />
              )}
              Appliquer le preset
            </Button>
          </div>

          {currentPreset && (
            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <div className="mb-2 font-medium">
                Modèles inclus ({currentPreset.templates.length})
              </div>
              <div className="flex flex-wrap gap-2">
                {currentPreset.templates.map((t) => (
                  <Badge key={t.name} variant="secondary" title={t.description}>
                    {t.name} · {t.weekly_hours}h
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div>
              <CardTitle>Plans configurés</CardTitle>
              <CardDescription>
                Chaque plan relie un modèle (ou une alternance de semaines) à une portée et une période.
              </CardDescription>
            </div>
            <div className="flex shrink-0 flex-wrap justify-end gap-2">
              <Button size="sm" variant="secondary" onClick={openCreatePlan}>
                <Plus className="mr-1 h-4 w-4" />
                Nouveau plan
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => batchMutation.mutate(true)}
                disabled={batchMutation.isPending || plans.length === 0}
              >
                {batchMutation.isPending ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}
                Aperçu société
              </Button>
              <Button
                size="sm"
                onClick={() => batchMutation.mutate(false)}
                disabled={batchMutation.isPending || plans.length === 0}
              >
                <Wand2 className="mr-1 h-4 w-4" />
                Générer toute la société 2026
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {plansQuery.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
            </div>
          ) : plans.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucun plan. Appliquez un preset ci-dessus pour démarrer.
            </p>
          ) : (
            <ul className="space-y-2">
              {plans.map((plan) => (
                <PlanRow
                  key={plan.id}
                  plan={plan}
                  busy={generateMutation.isPending && activePlanId === plan.id}
                  onPreview={() =>
                    generateMutation.mutate({ planId: plan.id, dryRun: true })
                  }
                  onGenerate={() =>
                    generateMutation.mutate({ planId: plan.id, dryRun: false })
                  }
                  onEdit={() => openEditPlan(plan)}
                  onDuplicate={() => openDuplicatePlan(plan)}
                  onToggleActive={() => toggleActiveMutation.mutate(plan)}
                  onDelete={() => deleteMutation.mutate(plan.id)}
                />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {batchResult && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {batchResult.status === 'preview' ? 'Aperçu société (non enregistré)' : 'Société générée'}
            </CardTitle>
            <CardDescription>
              {batchResult.plans_processed} plan(s) · {batchResult.employee_writes} calendrier(s)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {batchResult.plans.map((p) => (
              <div key={p.plan_id} className="flex justify-between gap-2 text-sm">
                <span className="truncate">
                  {p.plan_name}
                  <span className="ml-1 text-xs text-muted-foreground">
                    ({SCOPE_LABELS[p.scope_type] ?? p.scope_type})
                  </span>
                </span>
                <span className="shrink-0 text-muted-foreground">
                  {p.status === 'skipped' ? (p.reason ?? 'ignoré') : `${p.employee_count} salarié(s)`}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {preview && <PreviewCard result={preview} />}

      <SchedulePlanDialog
        open={planDialogOpen}
        onOpenChange={setPlanDialogOpen}
        companyId={companyId}
        plan={editingPlan}
        duplicate={duplicating}
      />
    </div>
  );
}

function PlanRow({
  plan,
  busy,
  onPreview,
  onGenerate,
  onEdit,
  onDuplicate,
  onToggleActive,
  onDelete,
}: {
  plan: SchedulePlan;
  busy: boolean;
  onPreview: () => void;
  onGenerate: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
  onToggleActive: () => void;
  onDelete: () => void;
}) {
  const hasCycle = (plan.template_cycle?.length ?? 0) > 1;
  const canGenerate = (plan.template_cycle?.length ?? 0) >= 1;
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate font-medium">{plan.name}</span>
          {!plan.is_active && <Badge variant="outline">Inactif</Badge>}
          {plan.status === 'applied' && <Badge variant="outline">Appliqué</Badge>}
          {hasCycle && <Badge variant="secondary">Alternance ×{plan.template_cycle.length}</Badge>}
          {plan.needs_confirmation && (
            <Badge variant="destructive">À confirmer</Badge>
          )}
        </div>
        <div className="text-xs text-muted-foreground">
          {SCOPE_LABELS[plan.scope_type] ?? plan.scope_type} · {plan.start_date}
          {plan.end_date ? ` → ${plan.end_date}` : ''}
        </div>
        {plan.notes && (
          <div className="mt-1 text-xs italic text-amber-700">{plan.notes}</div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <Button size="icon" variant="ghost" className="h-8 w-8" title="Modifier" onClick={onEdit}>
          <Pencil className="h-4 w-4" />
        </Button>
        <Button size="icon" variant="ghost" className="h-8 w-8" title="Dupliquer" onClick={onDuplicate}>
          <Copy className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8"
          title={plan.is_active ? 'Désactiver' : 'Activer'}
          onClick={onToggleActive}
        >
          <Power className={plan.is_active ? 'h-4 w-4 text-emerald-600' : 'h-4 w-4 text-muted-foreground'} />
        </Button>
        <Button size="icon" variant="ghost" className="h-8 w-8" title="Supprimer" onClick={onDelete}>
          <Trash2 className="h-4 w-4" />
        </Button>
        <Button size="sm" variant="outline" onClick={onPreview} disabled={busy || !canGenerate}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Aperçu'}
        </Button>
        <Button size="sm" onClick={onGenerate} disabled={busy || !canGenerate}>
          <Wand2 className="mr-1 h-4 w-4" />
          Générer 2026
        </Button>
      </div>
    </li>
  );
}

function PreviewCard({ result }: { result: GenerationResult }) {
  const isPreview = result.status === 'preview';
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          {isPreview ? 'Aperçu (non enregistré)' : 'Génération appliquée'}
        </CardTitle>
        <CardDescription>
          {result.employee_count ?? 0} salarié(s) · {result.start_date} → {result.end_date}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {result.employees.slice(0, 8).map((emp) => {
          const firstMonth = emp.months[0];
          const totals = firstMonth ? Object.values(firstMonth.weekly_totals) : [];
          const sample = totals.slice(0, 4).map((h) => `${h}h`).join(' · ');
          return (
            <div key={emp.employee_id} className="flex justify-between gap-2 text-sm">
              <span className="truncate">
                {emp.name || emp.employee_id}
                {emp.is_forfait && <span className="ml-1 text-xs text-muted-foreground">(forfait)</span>}
              </span>
              <span className="shrink-0 text-muted-foreground">
                {emp.months.length} mois · {sample || '—'}
              </span>
            </div>
          );
        })}
        {result.employees.length > 8 && (
          <p className="text-xs text-muted-foreground">
            … et {result.employees.length - 8} autre(s) salarié(s).
          </p>
        )}
      </CardContent>
    </Card>
  );
}
