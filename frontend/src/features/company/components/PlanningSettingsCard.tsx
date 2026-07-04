import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarClock, Plus, Trash2 } from 'lucide-react';
import { getCatalog, type CollectiveAgreementCatalog } from '@/api/collectiveAgreements';
import {
  createShiftType,
  deleteShiftType,
  getPlanningSettings,
  getShiftTypes,
  applyIndustrial3x8Preset,
  updatePlanningSettings,
  updateShiftType,
  type NightWindow,
  type ShiftType,
  type ShiftTypeCreatePayload,
} from '@/api/planning';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
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

const DEFAULT_NIGHT_WINDOWS: NightWindow[] = [
  { start: '22:00', end: '06:00', rate: 0.5 },
  { start: '05:00', end: '06:00', rate: 0.5 },
];

function formatTime(value?: string | null): string {
  if (!value) return '';
  return value.slice(0, 5);
}

function emptyShiftTypeDraft(): ShiftTypeCreatePayload {
  return {
    code: '',
    label: '',
    color: '#6366f1',
    default_start: '09:00',
    default_end: '17:00',
    allows_overnight: false,
    meal_allowance_eligible: true,
    paid_break_minutes: 0,
    night_windows: [],
  };
}

export default function PlanningSettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: queryKeys.planningSettings(activeCompanyId),
    queryFn: getPlanningSettings,
    enabled: Boolean(activeCompanyId),
  });

  const { data: shiftTypes = [], isLoading: typesLoading } = useQuery({
    queryKey: queryKeys.planningShiftTypes(activeCompanyId),
    queryFn: getShiftTypes,
    enabled: Boolean(activeCompanyId),
  });

  const { data: catalog = [] } = useQuery({
    queryKey: ['collective-agreements', 'catalog', 'planning'],
    queryFn: async () => {
      const res = await getCatalog({ active_only: true });
      return res.data ?? [];
    },
  });

  const [ccId, setCcId] = useState<string | null>(null);
  const [teamView, setTeamView] = useState(false);
  const [metricsEnabled, setMetricsEnabled] = useState(true);
  const [autoGenerate, setAutoGenerate] = useState(false);
  const [paidBreaksInBase, setPaidBreaksInBase] = useState(false);
  const [draft, setDraft] = useState<ShiftTypeCreatePayload>(emptyShiftTypeDraft());

  useEffect(() => {
    if (!settings) return;
    setCcId(settings.collective_agreement_id);
    setTeamView(settings.team_view_default);
    setMetricsEnabled(settings.payroll_shift_metrics_enabled);
    setAutoGenerate(settings.auto_generate_payroll_variables_before_payslip);
    setPaidBreaksInBase(settings.paid_breaks_included_in_base ?? false);
  }, [settings]);

  const saveSettings = useMutation({
    mutationFn: () =>
      updatePlanningSettings({
        collective_agreement_id: ccId,
        team_view_default: teamView,
        payroll_shift_metrics_enabled: metricsEnabled,
        auto_generate_payroll_variables_before_payslip: autoGenerate,
        paid_breaks_included_in_base: paidBreaksInBase,
      }),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.planningSettings(activeCompanyId), saved);
      queryClient.invalidateQueries({
        queryKey: queryKeys.planningShiftTypes(activeCompanyId),
      });
      toast({ title: 'Paramètres planning enregistrés' });
    },
  });

  const createType = useMutation({
    mutationFn: () => createShiftType(draft),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.planningShiftTypes(activeCompanyId),
      });
      setDraft(emptyShiftTypeDraft());
      toast({ title: 'Type de poste créé' });
    },
  });

  const patchType = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<ShiftType> }) =>
      updateShiftType(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.planningShiftTypes(activeCompanyId),
      });
    },
  });

  const removeType = useMutation({
    mutationFn: (id: string) => deleteShiftType(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.planningShiftTypes(activeCompanyId),
      });
      toast({ title: 'Type de poste désactivé' });
    },
  });

  const applyIndustrialPreset = useMutation({
    mutationFn: applyIndustrial3x8Preset,
    onSuccess: (result) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.planningShiftTypes(activeCompanyId),
      });
      toast({
        title: 'Modèle industriel 3×8 appliqué',
        description: `Créés : ${result.created_shift_types.join(', ') || 'aucun'}`,
      });
    },
    onError: () => {
      toast({
        title: 'Erreur',
        description: 'Vérifiez la CC planning et les codes déjà existants.',
        variant: 'destructive',
      });
    },
  });

  const applyTemplate3x8 = () => {
    const templates: ShiftTypeCreatePayload[] = [
      {
        code: 'MATIN',
        label: 'Matin',
        color: '#22c55e',
        default_start: '05:00',
        default_end: '13:00',
        allows_overnight: false,
        meal_allowance_eligible: true,
        paid_break_minutes: 20,
        unpaid_break_minutes: 30,
        night_windows: DEFAULT_NIGHT_WINDOWS,
      },
      {
        code: 'APREM',
        label: 'Après-midi',
        color: '#3b82f6',
        default_start: '13:00',
        default_end: '21:00',
        allows_overnight: false,
        meal_allowance_eligible: true,
        paid_break_minutes: 20,
        unpaid_break_minutes: 30,
        night_windows: DEFAULT_NIGHT_WINDOWS,
      },
      {
        code: 'NUIT',
        label: 'Nuit',
        color: '#6366f1',
        default_start: '22:00',
        default_end: '06:00',
        allows_overnight: true,
        meal_allowance_eligible: true,
        paid_break_minutes: 20,
        unpaid_break_minutes: 30,
        night_windows: DEFAULT_NIGHT_WINDOWS,
      },
    ];
    Promise.all(templates.map((t) => createShiftType(t)))
      .then(() => {
        queryClient.invalidateQueries({
          queryKey: queryKeys.planningShiftTypes(activeCompanyId),
        });
        toast({ title: 'Modèle 3×8 appliqué (3 types de poste)' });
      })
      .catch(() => {
        toast({
          title: 'Erreur',
          description: 'Vérifiez la CC planning et les codes déjà existants.',
          variant: 'destructive',
        });
      });
  };

  if (settingsLoading) {
    return <Skeleton className="h-48 w-full" />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarClock className="h-5 w-5" />
          Planning équipes
        </CardTitle>
        <CardDescription>
          Convention collective planning, types de poste (panier, nuit, pause) et options paie.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Convention collective (planning)</Label>
            <Select
              value={ccId ?? '__none__'}
              onValueChange={(v) => setCcId(v === '__none__' ? null : v)}
              disabled={!canEdit}
            >
              <SelectTrigger>
                <SelectValue placeholder="Choisir une CC" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Non définie</SelectItem>
                {(catalog as CollectiveAgreementCatalog[]).map((cc) => (
                  <SelectItem key={cc.id} value={cc.id}>
                    {cc.name} ({cc.idcc})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="team-view">Vue équipe par défaut</Label>
              <Switch
                id="team-view"
                checked={teamView}
                onCheckedChange={setTeamView}
                disabled={!canEdit}
              />
            </div>
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="metrics">Métriques paie (nuit / pause)</Label>
              <Switch
                id="metrics"
                checked={metricsEnabled}
                onCheckedChange={setMetricsEnabled}
                disabled={!canEdit}
              />
            </div>
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="auto-gen">Auto-générer variables avant bulletin</Label>
              <Switch
                id="auto-gen"
                checked={autoGenerate}
                onCheckedChange={setAutoGenerate}
                disabled={!canEdit}
              />
            </div>
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="paid-in-base">Pauses payées incluses dans le salaire de base</Label>
              <Switch
                id="paid-in-base"
                checked={paidBreaksInBase}
                onCheckedChange={setPaidBreaksInBase}
                disabled={!canEdit}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Si activé, pas de ligne « Pause rémunérée » séparée sur le bulletin (détail repas
              via modèles de semaine / pointage).
            </p>
          </div>
        </div>

        {canEdit && (
          <Button
            onClick={() => saveSettings.mutate()}
            disabled={saveSettings.isPending}
          >
            Enregistrer les paramètres
          </Button>
        )}

        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-sm font-medium">Types de poste</h4>
            {canEdit && ccId && (
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={applyIndustrialPreset.isPending}
                  onClick={() => applyIndustrialPreset.mutate()}
                >
                  Modèle 3×8 industriel (4h–20h)
                </Button>
                <Button variant="outline" size="sm" onClick={applyTemplate3x8}>
                  Modèle 3×8 standard
                </Button>
              </div>
            )}
          </div>
          {typesLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Libellé</TableHead>
                  <TableHead>Horaires</TableHead>
                  <TableHead>Payées (min)</TableHead>
                  <TableHead>Repas (min)</TableHead>
                  <TableHead>Panier</TableHead>
                  <TableHead>Nuit</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {shiftTypes.map((st) => (
                  <TableRow key={st.id}>
                    <TableCell>{st.code}</TableCell>
                    <TableCell>{st.label}</TableCell>
                    <TableCell>
                      {formatTime(st.default_start)} – {formatTime(st.default_end)}
                      {st.allows_overnight ? ' (nuit)' : ''}
                    </TableCell>
                    <TableCell>
                      {canEdit ? (
                        <Input
                          type="number"
                          className="w-20"
                          defaultValue={st.paid_break_minutes ?? 0}
                          onBlur={(e) => {
                            const v = Number(e.target.value) || 0;
                            if (v !== (st.paid_break_minutes ?? 0)) {
                              patchType.mutate({
                                id: st.id,
                                payload: { paid_break_minutes: v },
                              });
                            }
                          }}
                        />
                      ) : (
                        st.paid_break_minutes ?? 0
                      )}
                    </TableCell>
                    <TableCell>
                      {canEdit ? (
                        <Input
                          type="number"
                          className="w-20"
                          defaultValue={st.unpaid_break_minutes ?? 0}
                          onBlur={(e) => {
                            const v = Number(e.target.value) || 0;
                            if (v !== (st.unpaid_break_minutes ?? 0)) {
                              patchType.mutate({
                                id: st.id,
                                payload: { unpaid_break_minutes: v },
                              });
                            }
                          }}
                        />
                      ) : (
                        st.unpaid_break_minutes ?? 0
                      )}
                    </TableCell>
                    <TableCell>
                      {canEdit ? (
                        <Checkbox
                          checked={st.meal_allowance_eligible ?? true}
                          onCheckedChange={(checked) =>
                            patchType.mutate({
                              id: st.id,
                              payload: { meal_allowance_eligible: Boolean(checked) },
                            })
                          }
                        />
                      ) : st.meal_allowance_eligible ? 'Oui' : 'Non'}
                    </TableCell>
                    <TableCell>
                      {(st.night_windows?.length ?? 0) > 0 ? 'Configurée' : '—'}
                    </TableCell>
                    {canEdit && (
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeType.mutate(st.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
                {shiftTypes.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8} className="text-muted-foreground">
                      Aucun type de poste. Configurez la CC planning puis créez des types
                      ou appliquez le modèle 3×8.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </div>

        {canEdit && ccId && (
          <div className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Code</Label>
              <Input
                value={draft.code}
                onChange={(e) => setDraft({ ...draft, code: e.target.value.toUpperCase() })}
                placeholder="MATIN"
              />
            </div>
            <div className="space-y-2">
              <Label>Libellé</Label>
              <Input
                value={draft.label}
                onChange={(e) => setDraft({ ...draft, label: e.target.value })}
                placeholder="Matin"
              />
            </div>
            <div className="space-y-2">
              <Label>Début</Label>
              <Input
                type="time"
                value={draft.default_start ?? ''}
                onChange={(e) => setDraft({ ...draft, default_start: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Fin</Label>
              <Input
                type="time"
                value={draft.default_end ?? ''}
                onChange={(e) => setDraft({ ...draft, default_end: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Pause payée (minutes)</Label>
              <Input
                type="number"
                value={draft.paid_break_minutes ?? 0}
                onChange={(e) =>
                  setDraft({ ...draft, paid_break_minutes: Number(e.target.value) || 0 })
                }
              />
            </div>
            <div className="flex flex-col gap-2 justify-end">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="overnight"
                  checked={draft.allows_overnight}
                  onCheckedChange={(c) =>
                    setDraft({ ...draft, allows_overnight: Boolean(c) })
                  }
                />
                <Label htmlFor="overnight">Poste de nuit (fin &lt; début)</Label>
              </div>
              <div className="flex items-center gap-2">
                <Checkbox
                  id="meal"
                  checked={draft.meal_allowance_eligible}
                  onCheckedChange={(c) =>
                    setDraft({ ...draft, meal_allowance_eligible: Boolean(c) })
                  }
                />
                <Label htmlFor="meal">Éligible panier repas</Label>
              </div>
            </div>
            <div className="sm:col-span-2 flex gap-2">
              <Button
                variant="outline"
                onClick={() =>
                  setDraft({ ...draft, night_windows: DEFAULT_NIGHT_WINDOWS })
                }
              >
                Plages nuit standard (22h–6h, 5h–6h)
              </Button>
              <Button
                disabled={!draft.code || !draft.label || createType.isPending}
                onClick={() => createType.mutate()}
              >
                <Plus className="mr-2 h-4 w-4" />
                Ajouter le type
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
