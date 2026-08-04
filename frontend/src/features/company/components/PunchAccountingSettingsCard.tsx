import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Clock, Loader2, Plus, Trash2 } from 'lucide-react';
import {
  applyPunchAccountingPreset,
  createPunchShiftSlot,
  deletePunchShiftSlot,
  getPunchAccountingSettings,
  listPunchOvertimeReviews,
  listPunchShiftSlots,
  updatePunchAccountingSettings,
  updatePunchOvertimeReview,
  updatePunchShiftSlot,
  type PunchAccountingSettings,
  type PunchShiftSlot,
} from '@/api/punchAccounting';
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
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { queryKeys } from '@/lib/queryKeys';

const now = new Date();

export default function PunchAccountingSettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const { data: settings, isLoading } = useQuery({
    queryKey: queryKeys.punchAccountingSettings(activeCompanyId),
    queryFn: getPunchAccountingSettings,
    enabled: Boolean(activeCompanyId),
  });

  const { data: slots = [] } = useQuery({
    queryKey: queryKeys.punchShiftSlots(activeCompanyId),
    queryFn: listPunchShiftSlots,
    enabled: Boolean(activeCompanyId),
  });

  const { data: pendingReviews = [] } = useQuery({
    queryKey: queryKeys.punchOvertimeReviews(activeCompanyId, now.getFullYear(), now.getMonth() + 1),
    queryFn: () => listPunchOvertimeReviews(now.getFullYear(), now.getMonth() + 1, 'pending'),
    enabled: Boolean(activeCompanyId) && Boolean(settings?.enabled),
  });

  const [form, setForm] = useState<PunchAccountingSettings | null>(null);

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  const saveMut = useMutation({
    mutationFn: updatePunchAccountingSettings,
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.punchAccountingSettings(activeCompanyId), saved);
      setForm(saved);
      toast({ title: 'Paramètres enregistrés' });
    },
    onError: () => {
      toast({ title: 'Erreur', description: 'Enregistrement impossible.', variant: 'destructive' });
    },
  });

  const presetMut = useMutation({
    mutationFn: () => applyPunchAccountingPreset('three_daily_slots'),
    onSuccess: (result) => {
      queryClient.setQueryData(
        queryKeys.punchAccountingSettings(activeCompanyId),
        result.settings,
      );
      queryClient.setQueryData(queryKeys.punchShiftSlots(activeCompanyId), result.slots);
      setForm(result.settings);
      toast({ title: 'Preset appliqué', description: '3 créneaux journaliers configurés.' });
    },
    onError: () => {
      toast({ title: 'Erreur', variant: 'destructive' });
    },
  });

  const paidLunchPresetMut = useMutation({
    mutationFn: () => applyPunchAccountingPreset('equipe_paid_lunch'),
    onSuccess: (result) => {
      queryClient.setQueryData(
        queryKeys.punchAccountingSettings(activeCompanyId),
        result.settings,
      );
      queryClient.setQueryData(queryKeys.punchShiftSlots(activeCompanyId), result.slots);
      setForm(result.settings);
      toast({
        title: 'Preset équipes appliqué',
        description: 'Créneaux avec pause déjeuner payée (mode legacy).',
      });
    },
    onError: () => {
      toast({ title: 'Erreur', variant: 'destructive' });
    },
  });

  const industrialPresetMut = useMutation({
    mutationFn: () => applyPunchAccountingPreset('industrial_3x8_breaks'),
    onSuccess: (result) => {
      queryClient.setQueryData(
        queryKeys.punchAccountingSettings(activeCompanyId),
        result.settings,
      );
      queryClient.setQueryData(queryKeys.punchShiftSlots(activeCompanyId), result.slots);
      setForm(result.settings);
      toast({
        title: 'Preset 3×8 industriel appliqué',
        description: '2×10 min payées + 30 min repas déduite par créneau.',
      });
    },
    onError: () => {
      toast({ title: 'Erreur', variant: 'destructive' });
    },
  });

  const slotPatchMut = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof updatePunchShiftSlot>[1] }) =>
      updatePunchShiftSlot(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.punchShiftSlots(activeCompanyId) });
    },
  });

  const addSlotMut = useMutation({
    mutationFn: () =>
      createPunchShiftSlot({
        label: 'Nouveau créneau',
        entry_time: '08:00',
        exit_time: '17:00',
        sort_order: slots.length,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.punchShiftSlots(activeCompanyId) });
    },
  });

  const deleteSlotMut = useMutation({
    mutationFn: deletePunchShiftSlot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.punchShiftSlots(activeCompanyId) });
    },
  });

  const reviewMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'approved' | 'rejected' }) =>
      updatePunchOvertimeReview(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.punchOvertimeReviews(
          activeCompanyId,
          now.getFullYear(),
          now.getMonth() + 1,
        ),
      });
      toast({ title: 'Décision enregistrée' });
    },
  });

  if (isLoading || !form) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-8">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          <span className="text-sm text-muted-foreground">Chargement…</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Clock className="h-4 w-4" />
          Comptabilisation des pointages
        </CardTitle>
        <CardDescription>
          Grilles horaires, tolérance et validation des heures supplémentaires détectées au pointage.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Switch
              id="punch-enabled"
              checked={form.enabled}
              disabled={!canEdit}
              onCheckedChange={(enabled) => {
                const next = { ...form, enabled };
                setForm(next);
                saveMut.mutate({ enabled });
              }}
            />
            <Label htmlFor="punch-enabled">Activer le moteur de comptabilisation</Label>
          </div>
          {canEdit && (
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={presetMut.isPending}
                onClick={() => presetMut.mutate()}
              >
                Preset : 3 créneaux journaliers
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={paidLunchPresetMut.isPending}
                onClick={() => paidLunchPresetMut.mutate()}
              >
                Preset : équipes pause payée
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={industrialPresetMut.isPending}
                onClick={() => industrialPresetMut.mutate()}
              >
                Preset : 3×8 industriel
              </Button>
            </div>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="tolerance">Tolérance (minutes)</Label>
            <Input
              id="tolerance"
              type="number"
              min={0}
              max={120}
              value={form.tolerance_minutes}
              disabled={!canEdit}
              onChange={(e) =>
                setForm({ ...form, tolerance_minutes: Number(e.target.value) || 0 })
              }
              onBlur={() => saveMut.mutate({ tolerance_minutes: form.tolerance_minutes })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="break">Pause repas déduite par défaut (min)</Label>
            <Input
              id="break"
              type="number"
              min={0}
              max={180}
              value={form.default_break_deduct_minutes}
              disabled={!canEdit}
              onChange={(e) =>
                setForm({
                  ...form,
                  default_break_deduct_minutes: Number(e.target.value) || 0,
                })
              }
              onBlur={() =>
                saveMut.mutate({ default_break_deduct_minutes: form.default_break_deduct_minutes })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="break-threshold">
              Pause ignorée en deçà de (min de présence)
            </Label>
            <Input
              id="break-threshold"
              type="number"
              min={0}
              max={960}
              value={form.break_threshold_minutes}
              disabled={!canEdit}
              onChange={(e) =>
                setForm({
                  ...form,
                  break_threshold_minutes: Number(e.target.value) || 0,
                })
              }
              onBlur={() =>
                saveMut.mutate({
                  break_threshold_minutes: form.break_threshold_minutes,
                })
              }
            />
            <p className="text-xs text-muted-foreground">
              Une demi-journée plus courte que ce seuil ne subit aucune pause.
              0 : la pause s&apos;applique à toutes les journées.
            </p>
          </div>
          <div className="space-y-2">
            <Label>Détection du créneau</Label>
            <Select
              value={form.slot_detection}
              disabled={!canEdit}
              onValueChange={(slot_detection) => {
                setForm({ ...form, slot_detection: slot_detection as PunchAccountingSettings['slot_detection'] });
                saveMut.mutate({ slot_detection: slot_detection as PunchAccountingSettings['slot_detection'] });
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="shift_code">Code horaire import</SelectItem>
                <SelectItem value="nearest_entry">Entrée la plus proche</SelectItem>
                <SelectItem value="planning_first">Planning d&apos;abord</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label>Créneaux horaires</Label>
            {canEdit && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => addSlotMut.mutate()}
                disabled={addSlotMut.isPending}
              >
                <Plus className="mr-1 h-4 w-4" />
                Ajouter
              </Button>
            )}
          </div>
          {slots.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun créneau — appliquez un preset ou ajoutez-en.</p>
          ) : (
            <div className="space-y-3">
              {slots.map((slot: PunchShiftSlot) => (
                <div
                  key={slot.id}
                  className="rounded-md border px-3 py-2 text-sm space-y-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">
                      {slot.code ? `[${slot.code}] ` : ''}
                      {slot.label || `${slot.entry_time} – ${slot.exit_time}`}
                    </span>
                    {canEdit && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => deleteSlotMut.mutate(slot.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                    <div className="space-y-1">
                      <Label className="text-xs">Entrée</Label>
                      <Input
                        type="time"
                        className="h-8"
                        defaultValue={slot.entry_time?.slice(0, 5)}
                        disabled={!canEdit}
                        onBlur={(e) => {
                          const v = e.target.value;
                          if (v && v !== slot.entry_time?.slice(0, 5)) {
                            slotPatchMut.mutate({ id: slot.id, payload: { entry_time: v } });
                          }
                        }}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Sortie</Label>
                      <Input
                        type="time"
                        className="h-8"
                        defaultValue={slot.exit_time?.slice(0, 5)}
                        disabled={!canEdit}
                        onBlur={(e) => {
                          const v = e.target.value;
                          if (v && v !== slot.exit_time?.slice(0, 5)) {
                            slotPatchMut.mutate({ id: slot.id, payload: { exit_time: v } });
                          }
                        }}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Repas déduit (min)</Label>
                      <Input
                        type="number"
                        className="h-8"
                        min={0}
                        defaultValue={slot.break_deduct_minutes}
                        disabled={!canEdit}
                        onBlur={(e) => {
                          const v = Number(e.target.value) || 0;
                          if (v !== slot.break_deduct_minutes) {
                            slotPatchMut.mutate({
                              id: slot.id,
                              payload: { break_deduct_minutes: v },
                            });
                          }
                        }}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Payées incluses (min)</Label>
                      <Input
                        type="number"
                        className="h-8"
                        min={0}
                        defaultValue={slot.paid_break_minutes ?? 0}
                        disabled={!canEdit}
                        onBlur={(e) => {
                          const v = Number(e.target.value) || 0;
                          if (v !== (slot.paid_break_minutes ?? 0)) {
                            slotPatchMut.mutate({
                              id: slot.id,
                              payload: { paid_break_minutes: v },
                            });
                          }
                        }}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Déjeuner payé (legacy)</Label>
                      <div className="flex h-8 items-center">
                        <Switch
                          checked={slot.paid_lunch_break}
                          disabled={!canEdit}
                          onCheckedChange={(paid_lunch_break) =>
                            slotPatchMut.mutate({
                              id: slot.id,
                              payload: { paid_lunch_break },
                            })
                          }
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {form.enabled && pendingReviews.length > 0 && (
          <div className="space-y-2 rounded-md border border-amber-200 bg-amber-50/50 p-3 dark:border-amber-900 dark:bg-amber-950/20">
            <Label>HS pointage en attente ({pendingReviews.length})</Label>
            <ul className="space-y-2">
              {pendingReviews.map((review) => (
                <li
                  key={review.id}
                  className="flex flex-wrap items-center justify-between gap-2 text-sm"
                >
                  <span>
                    {review.employee_name ?? review.employee_id} — {review.work_date} —{' '}
                    {review.overtime_hours.toFixed(2)} h
                    {review.raw_entry_time && review.raw_exit_time
                      ? ` (${review.raw_entry_time} → ${review.raw_exit_time})`
                      : ''}
                  </span>
                  {canEdit && (
                    <span className="flex gap-1">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => reviewMut.mutate({ id: review.id, status: 'approved' })}
                      >
                        Valider
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => reviewMut.mutate({ id: review.id, status: 'rejected' })}
                      >
                        Rejeter
                      </Button>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
