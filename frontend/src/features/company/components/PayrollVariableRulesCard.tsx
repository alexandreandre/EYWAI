import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Coins, Trash2 } from 'lucide-react';
import { getBonusTypes, type BonusType } from '@/api/bonusTypes';
import { getShiftTypes, type ShiftType } from '@/api/planning';
import {
  applyAstreinteEquipesPreset,
  applyShiftTeamsPayrollPreset,
  createPayrollVariableRule,
  deletePayrollVariableRule,
  generatePayrollVariables,
  listPayrollVariableRules,
  type AstreinteKmRuleConditions,
  type AstreinteWeekTieredConditions,
  type AstreinteWeekendMajorationConditions,
  type PayrollVariableGenerateResult,
  type PayrollVariablePreviewItem,
  type PayrollVariableRule,
  type PresenceWeekRuleConditions,
} from '@/api/payrollVariables';
import { ABSENCE_TYPE_LABELS } from '@/lib/employeeAbsencesUtils';
import { Alert, AlertDescription } from '@/components/ui/alert';
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

const RULE_TYPE_LABELS: Record<string, string> = {
  fixed_monthly: 'Montant fixe mensuel',
  per_astreinte_week: 'Par semaine d\'astreinte (simple)',
  per_astreinte_week_tiered: 'Astreinte hebdo (Noël / pont)',
  per_astreinte_weekend_majoration: 'Majoration astreinte WE',
  per_shift_type: 'Par type de poste',
  per_modulation_payout: 'Prime liquidation modulation',
  per_night_hour: 'Par heure de nuit',
  per_astreinte_weekend_km: 'Indemnité km astreinte',
  per_week_without_absence: 'Par semaine sans absence',
};

const DEFAULT_ASTREINTE_TIERED: AstreinteWeekTieredConditions = {
  amount_normal: 176.18,
  amount_christmas: 352.36,
  amount_bridge: 250,
  christmas_mode: 'replace',
  bridge_mode: 'add',
  christmas_detection: 'iso_dec_25',
  bridge_requires_astreinte_on_day: true,
};

const DEFAULT_ASTREINTE_WEEKEND_MAJ: AstreinteWeekendMajorationConditions = {
  weekday_rates: { '5': 0.25, '6': 1.0 },
  min_hours: 1,
  flat_hours: 1,
  requires_astreinte_same_iso_week: true,
  weekend_weekday_numbers: [5, 6],
};

const DEFAULT_ASTREINTE_KM_CONDITIONS: AstreinteKmRuleConditions = {
  km_free_threshold_one_way: 10,
  round_trip_multiplier: 2,
  requires_astreinte: true,
  requires_weekend_work: true,
  astreinte_link_mode: 'same_iso_week',
  quantity_mode: 'once_if_eligible',
  rate_mode: 'coefficient_a',
  vehicle_type_default: 'voitures',
};

const SKIP_REASON_LABELS: Record<string, string> = {
  below_threshold: 'Distance sous le seuil km',
  no_astreinte: 'Pas d\'astreinte ce mois',
  no_weekend_work: 'Pas d\'heures week-end pointées',
  astreinte_weekend_not_linked: 'Astreinte et week-end non liés',
  employee_not_configured: 'Fiche salarié non configurée',
  missing_distance_or_cv: 'Distance ou CV manquant',
  bareme_missing: 'Barème km indisponible',
  zero_quantity: 'Quantité nulle',
};

const GENERATION_MODE_LABELS: Record<string, string> = {
  auto: 'Automatique (écrit les saisies)',
  suggest: 'Suggestion uniquement (aperçu)',
};

function formatPreviewDetail(item: PayrollVariablePreviewItem): string {
  const d = item.details;
  if (!d) return '';
  if (d.skip_reason) {
    return SKIP_REASON_LABELS[d.skip_reason] ?? d.skip_reason;
  }
  const parts: string[] = [];
  if (d.km_eligible != null) parts.push(`${d.km_eligible} km`);
  if (d.rate != null) parts.push(`${d.rate} €/km`);
  return parts.join(' · ');
}

function formatPreview(result: PayrollVariableGenerateResult): string {
  if (!result.preview.length) return 'Aucune ligne.';
  return result.preview
    .slice(0, 15)
    .map((p) => {
      const name = [p.first_name, p.last_name].filter(Boolean).join(' ') || p.employee_id;
      const detail = formatPreviewDetail(p);
      const line = `${name} — ${p.rule_label ?? p.rule_code}: ${p.quantity} × ${(p.amount / Math.max(p.quantity, 1)).toFixed(2)} € = ${p.amount.toFixed(2)} €`;
      return detail ? `${line} (${detail})` : line;
    })
    .join('\n');
}

export default function PayrollVariableRulesCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const now = new Date();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const { data: rules = [], isLoading } = useQuery({
    queryKey: queryKeys.payrollVariableRules(activeCompanyId),
    queryFn: listPayrollVariableRules,
    enabled: Boolean(activeCompanyId),
  });

  const { data: bonusTypes = [] } = useQuery({
    queryKey: ['bonus-types', activeCompanyId],
    queryFn: async () => {
      const res = await getBonusTypes();
      return res.data ?? [];
    },
    enabled: Boolean(activeCompanyId),
  });

  const { data: shiftTypes = [] } = useQuery({
    queryKey: queryKeys.planningShiftTypes(activeCompanyId),
    queryFn: getShiftTypes,
    enabled: Boolean(activeCompanyId),
  });

  const [draft, setDraft] = useState<Partial<PayrollVariableRule>>({
    code: '',
    label: '',
    rule_type: 'fixed_monthly',
    amount: 0,
    enabled: true,
    generation_mode: 'auto',
    conditions: {},
    sort_order: 0,
  });

  const [simulation, setSimulation] = useState<PayrollVariableGenerateResult | null>(null);
  const selectedShiftCodes = (draft.conditions?.shift_type_codes as string[] | undefined) ?? [];
  const isAstreinteKm = draft.rule_type === 'per_astreinte_weekend_km';
  const isTiered = draft.rule_type === 'per_astreinte_week_tiered';
  const isWeekendMaj = draft.rule_type === 'per_astreinte_weekend_majoration';
  const isPresenceWeek = draft.rule_type === 'per_week_without_absence';
  const noAmountRule = isAstreinteKm || isTiered || isWeekendMaj;
  const astreinteConditions = (draft.conditions ?? {}) as AstreinteKmRuleConditions;
  const tieredConditions = (draft.conditions ?? {}) as AstreinteWeekTieredConditions;
  const weekendMajConditions = (draft.conditions ?? {}) as AstreinteWeekendMajorationConditions;
  const presenceConditions = (draft.conditions ?? {}) as PresenceWeekRuleConditions;
  const selectedAbsenceTypes = presenceConditions.absence_types ?? [];

  const hasNightHourRule = rules.some((r) => r.rule_type === 'per_night_hour' && r.enabled);

  const setTieredCondition = <K extends keyof AstreinteWeekTieredConditions>(
    key: K,
    value: AstreinteWeekTieredConditions[K],
  ) => {
    setDraft({
      ...draft,
      conditions: { ...tieredConditions, [key]: value },
    });
  };

  const setWeekendMajCondition = <K extends keyof AstreinteWeekendMajorationConditions>(
    key: K,
    value: AstreinteWeekendMajorationConditions[K],
  ) => {
    setDraft({
      ...draft,
      conditions: { ...weekendMajConditions, [key]: value },
    });
  };

  const setAstreinteCondition = <K extends keyof AstreinteKmRuleConditions>(
    key: K,
    value: AstreinteKmRuleConditions[K],
  ) => {
    setDraft({
      ...draft,
      conditions: { ...astreinteConditions, [key]: value },
    });
  };

  const toggleShiftCode = (code: string) => {
    const next = selectedShiftCodes.includes(code)
      ? selectedShiftCodes.filter((c) => c !== code)
      : [...selectedShiftCodes, code];
    setDraft({
      ...draft,
      conditions: { ...draft.conditions, shift_type_codes: next },
    });
  };

  const toggleAbsenceType = (typeKey: string) => {
    const next = selectedAbsenceTypes.includes(typeKey)
      ? selectedAbsenceTypes.filter((t) => t !== typeKey)
      : [...selectedAbsenceTypes, typeKey];
    setDraft({
      ...draft,
      conditions: { ...presenceConditions, absence_types: next },
    });
  };

  const setPresenceCondition = <K extends keyof PresenceWeekRuleConditions>(
    key: K,
    value: PresenceWeekRuleConditions[K],
  ) => {
    setDraft({
      ...draft,
      conditions: { ...presenceConditions, [key]: value },
    });
  };

  const createRule = useMutation({
    mutationFn: () => {
      if (isPresenceWeek && selectedAbsenceTypes.length === 0) {
        throw new Error('Cochez au moins un type d\'absence disqualifiant.');
      }
      let conditions = draft.conditions || {};
      if (isAstreinteKm) {
        conditions = { ...DEFAULT_ASTREINTE_KM_CONDITIONS, ...astreinteConditions };
      } else if (isTiered) {
        conditions = { ...DEFAULT_ASTREINTE_TIERED, ...tieredConditions };
      } else if (isWeekendMaj) {
        conditions = { ...DEFAULT_ASTREINTE_WEEKEND_MAJ, ...weekendMajConditions };
      } else if (isPresenceWeek) {
        const perWeek = Number(draft.amount ?? presenceConditions.amount_per_week ?? 0);
        conditions = {
          ...presenceConditions,
          amount_per_week: perWeek,
          absence_types: selectedAbsenceTypes,
        };
      }
      const ruleAmount = noAmountRule
        ? null
        : isPresenceWeek
          ? Number(draft.amount ?? presenceConditions.amount_per_week ?? 0)
          : (draft.amount ?? 0);
      return createPayrollVariableRule({
        code: draft.code || 'rule',
        label: draft.label || 'Nouvelle règle',
        enabled: true,
        rule_type: draft.rule_type || 'fixed_monthly',
        amount: ruleAmount,
        bonus_type_id: draft.bonus_type_id ?? null,
        conditions,
        generation_mode:
          draft.generation_mode
          || (noAmountRule ? 'suggest' : 'auto'),
        sort_order: rules.length,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.payrollVariableRules(activeCompanyId),
      });
      toast({ title: 'Règle créée' });
      setDraft({
        code: '',
        label: '',
        rule_type: 'fixed_monthly',
        amount: 0,
        enabled: true,
        generation_mode: 'auto',
        conditions: {},
        sort_order: 0,
      });
    },
    onError: (err: Error) => {
      toast({
        title: 'Erreur',
        description: err.message || 'Création impossible.',
        variant: 'destructive',
      });
    },
  });

  const generate = useMutation({
    mutationFn: (dryRun: boolean) =>
      generatePayrollVariables(now.getFullYear(), now.getMonth() + 1, dryRun),
    onSuccess: (result) => {
      if (result.dry_run) setSimulation(result);
      toast({
        title: result.dry_run ? 'Simulation terminée' : 'Variables générées',
        description: `${result.preview.length} ligne(s) — ${result.written_count} écriture(s)`,
      });
    },
  });

  const applyPreset = useMutation({
    mutationFn: applyAstreinteEquipesPreset,
    onSuccess: (result) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.payrollVariableRules(activeCompanyId),
      });
      queryClient.invalidateQueries({ queryKey: ['bonus-types', activeCompanyId] });
      toast({
        title: 'Modèle astreinte appliqué',
        description: `${result.created_rules.length} règle(s), ${result.created_bonus_types.length} type(s) de prime créés.`,
      });
    },
  });

  const applyShiftTeamsPreset = useMutation({
    mutationFn: applyShiftTeamsPayrollPreset,
    onSuccess: (result) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.payrollVariableRules(activeCompanyId),
      });
      queryClient.invalidateQueries({ queryKey: ['bonus-types', activeCompanyId] });
      toast({
        title: 'Modèle équipes appliqué',
        description: `${result.created_rules.length} règle(s), ${result.created_bonus_types.length} type(s) de prime créés. Complétez les montants et codes export.`,
      });
    },
  });

  const removeRule = useMutation({
    mutationFn: (ruleId: string) => deletePayrollVariableRule(ruleId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.payrollVariableRules(activeCompanyId),
      });
      toast({ title: 'Règle supprimée' });
    },
  });

  const showShiftCodes = draft.rule_type === 'per_shift_type';

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Coins className="h-5 w-5" />
          Variables de paie récurrentes
        </CardTitle>
        <CardDescription>
          Productivité, astreintes, indemnités km — génération vers les saisies mensuelles.
          Pour l&apos;indemnité km astreinte, renseignez distance et CV sur la fiche salarié.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {hasNightHourRule && (
          <Alert className="border-amber-200 bg-amber-50/80">
            <AlertDescription>
              Une règle « Par heure de nuit » est active : ne cumulez pas avec les
              majorations nuit du planning (types de poste), sous peine de double comptage.
              Préférez les <strong>night_windows</strong> à 50 % sur les postes (code B_P4).
            </AlertDescription>
          </Alert>
        )}
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Libellé</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Montant</TableHead>
                <TableHead>Mode</TableHead>
                {canEdit && <TableHead className="w-12" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.code}</TableCell>
                  <TableCell>{r.label}</TableCell>
                  <TableCell>{RULE_TYPE_LABELS[r.rule_type] ?? r.rule_type}</TableCell>
                  <TableCell>{r.amount ?? '—'}</TableCell>
                  <TableCell>{GENERATION_MODE_LABELS[r.generation_mode] ?? r.generation_mode}</TableCell>
                  {canEdit && r.id && (
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Supprimer la règle"
                        onClick={() => removeRule.mutate(r.id!)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
              {rules.length === 0 && (
                <TableRow>
                  <TableCell colSpan={canEdit ? 6 : 5} className="text-muted-foreground">
                    Aucune règle configurée.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}

        {simulation && (
          <div className="rounded-lg border bg-muted/40 p-3 text-sm whitespace-pre-wrap">
            <p className="font-medium mb-2">
              Simulation {simulation.month}/{simulation.year} — {simulation.preview.length} ligne(s)
            </p>
            {formatPreview(simulation)}
            {simulation.preview.length > 15 && (
              <p className="text-muted-foreground mt-2">… et {simulation.preview.length - 15} autre(s)</p>
            )}
          </div>
        )}

        {canEdit && (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              disabled={applyPreset.isPending}
              onClick={() => applyPreset.mutate()}
            >
              Appliquer le modèle astreinte équipes
            </Button>
            <Button
              variant="secondary"
              disabled={applyShiftTeamsPreset.isPending}
              onClick={() => applyShiftTeamsPreset.mutate()}
            >
              Modèle équipes (paniers + prime nuit)
            </Button>
          </div>
        )}

        {canEdit && (
          <div className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Code</Label>
              <Input
                value={draft.code ?? ''}
                onChange={(e) => setDraft({ ...draft, code: e.target.value })}
                placeholder="panier_poste"
              />
            </div>
            <div className="space-y-2">
              <Label>Libellé</Label>
              <Input
                value={draft.label ?? ''}
                onChange={(e) => setDraft({ ...draft, label: e.target.value })}
                placeholder="Indemnité panier repas"
              />
            </div>
            <div className="space-y-2">
              <Label>Type de règle</Label>
              <Select
                value={draft.rule_type}
                onValueChange={(v) => {
                  const rt = v as PayrollVariableRule['rule_type'];
                  let conditions = draft.conditions ?? {};
                  let generation_mode = draft.generation_mode;
                  let amount = draft.amount;
                  if (rt === 'per_astreinte_weekend_km') {
                    conditions = { ...DEFAULT_ASTREINTE_KM_CONDITIONS };
                    generation_mode = 'suggest';
                    amount = null;
                  } else if (rt === 'per_astreinte_week_tiered') {
                    conditions = { ...DEFAULT_ASTREINTE_TIERED };
                    generation_mode = 'suggest';
                    amount = null;
                  } else if (rt === 'per_astreinte_weekend_majoration') {
                    conditions = { ...DEFAULT_ASTREINTE_WEEKEND_MAJ };
                    generation_mode = 'suggest';
                    amount = null;
                  } else if (rt === 'per_week_without_absence') {
                    conditions = { absence_types: [], amount_per_week: 6 };
                    generation_mode = 'auto';
                    amount = 6;
                  }
                  setDraft({
                    ...draft,
                    rule_type: rt,
                    conditions,
                    generation_mode,
                    amount,
                  });
                }}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(RULE_TYPE_LABELS).map(([k, label]) => (
                    <SelectItem key={k} value={k}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>
                {noAmountRule
                  ? 'Montant (calculé auto)'
                  : isPresenceWeek
                    ? 'Montant hebdomadaire (€)'
                    : 'Montant unitaire (€)'}
              </Label>
              <Input
                type="number"
                disabled={noAmountRule}
                value={noAmountRule ? '' : (draft.amount ?? 0)}
                placeholder={noAmountRule ? 'Voir conditions ci-dessous' : undefined}
                onChange={(e) =>
                  setDraft({ ...draft, amount: Number(e.target.value) || 0 })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Type de prime catalogue</Label>
              <Select
                value={draft.bonus_type_id ?? '__none__'}
                onValueChange={(v) =>
                  setDraft({
                    ...draft,
                    bonus_type_id: v === '__none__' ? null : v,
                  })
                }
              >
                <SelectTrigger><SelectValue placeholder="Optionnel" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Aucun (libellé règle)</SelectItem>
                  {(bonusTypes as BonusType[]).map((bt) => (
                    <SelectItem key={bt.id} value={bt.id}>
                      {bt.libelle}
                      {!bt.soumise_a_cotisations || !bt.soumise_a_impot ? ' (exonérée)' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Code export paie (optionnel)</Label>
              <Input
                value={String((draft.conditions as Record<string, unknown>)?.export_code ?? '')}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    conditions: {
                      ...draft.conditions,
                      export_code: e.target.value || undefined,
                    },
                  })
                }
                placeholder="SPEQ, B_P4…"
              />
            </div>
            <div className="space-y-2">
              <Label>Mode génération</Label>
              <Select
                value={draft.generation_mode ?? 'auto'}
                onValueChange={(v) =>
                  setDraft({
                    ...draft,
                    generation_mode: v as PayrollVariableRule['generation_mode'],
                  })
                }
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(GENERATION_MODE_LABELS).map(([k, label]) => (
                    <SelectItem key={k} value={k}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Auto : écrit dans les saisies mensuelles. Suggest : visible uniquement en simulation.
              </p>
            </div>

            {showShiftCodes && (
              <div className="space-y-2 sm:col-span-2">
                <Label>Types de poste concernés</Label>
                <div className="flex flex-wrap gap-3">
                  {(shiftTypes as ShiftType[]).map((st) => (
                    <label key={st.id} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={selectedShiftCodes.includes(st.code)}
                        onCheckedChange={() => toggleShiftCode(st.code)}
                      />
                      {st.code} — {st.label}
                    </label>
                  ))}
                  {shiftTypes.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      Configurez d&apos;abord les types de poste dans Planning équipes.
                    </p>
                  )}
                </div>
              </div>
            )}

            {isPresenceWeek && (
              <div className="space-y-3 sm:col-span-2">
                <Label>Types d&apos;absence qui annulent la prime (semaine ISO)</Label>
                <p className="text-xs text-muted-foreground">
                  Cochez explicitement les absences à surveiller — aucune sélection = règle inactive.
                </p>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(ABSENCE_TYPE_LABELS).map(([key, label]) => (
                    <label key={key} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={selectedAbsenceTypes.includes(key)}
                        onCheckedChange={() => toggleAbsenceType(key)}
                      />
                      {label}
                    </label>
                  ))}
                </div>
                <div className="space-y-2">
                  <Label>Postes verrouillés minimum / semaine (0 = ignoré)</Label>
                  <Input
                    type="number"
                    min={0}
                    value={presenceConditions.min_locked_shifts_per_week ?? 0}
                    onChange={(e) =>
                      setPresenceCondition(
                        'min_locked_shifts_per_week',
                        Number(e.target.value) || 0,
                      )
                    }
                  />
                </div>
              </div>
            )}

            {isTiered && (
              <>
                <div className="space-y-2">
                  <Label>Prime normale / semaine (€)</Label>
                  <Input
                    type="number"
                    value={tieredConditions.amount_normal ?? 176.18}
                    onChange={(e) =>
                      setTieredCondition('amount_normal', Number(e.target.value) || 0)
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Prime semaine Noël (€)</Label>
                  <Input
                    type="number"
                    value={tieredConditions.amount_christmas ?? 352.36}
                    onChange={(e) =>
                      setTieredCondition('amount_christmas', Number(e.target.value) || 0)
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Prime pont (€)</Label>
                  <Input
                    type="number"
                    value={tieredConditions.amount_bridge ?? 250}
                    onChange={(e) =>
                      setTieredCondition('amount_bridge', Number(e.target.value) || 0)
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Cumul Noël</Label>
                  <Select
                    value={tieredConditions.christmas_mode ?? 'replace'}
                    onValueChange={(v) =>
                      setTieredCondition('christmas_mode', v as 'replace' | 'add')
                    }
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="replace">Remplace la prime normale</SelectItem>
                      <SelectItem value="add">S&apos;ajoute à la prime normale</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Cumul pont</Label>
                  <Select
                    value={tieredConditions.bridge_mode ?? 'add'}
                    onValueChange={(v) =>
                      setTieredCondition('bridge_mode', v as 'add' | 'replace')
                    }
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="add">S&apos;ajoute (défaut)</SelectItem>
                      <SelectItem value="replace">Remplace la prime semaine</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}

            {isWeekendMaj && (
              <>
                <div className="space-y-2">
                  <Label>Majoration samedi (0,25 = 25 %)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={weekendMajConditions.weekday_rates?.['5'] ?? 0.25}
                    onChange={(e) =>
                      setWeekendMajCondition('weekday_rates', {
                        ...weekendMajConditions.weekday_rates,
                        '5': Number(e.target.value) || 0,
                        '6': weekendMajConditions.weekday_rates?.['6'] ?? 1,
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Majoration dimanche (1 = 100 %)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={weekendMajConditions.weekday_rates?.['6'] ?? 1}
                    onChange={(e) =>
                      setWeekendMajCondition('weekday_rates', {
                        ...weekendMajConditions.weekday_rates,
                        '5': weekendMajConditions.weekday_rates?.['5'] ?? 0.25,
                        '6': Number(e.target.value) || 0,
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Heures minimum pointées</Label>
                  <Input
                    type="number"
                    step="0.5"
                    value={weekendMajConditions.min_hours ?? 1}
                    onChange={(e) =>
                      setWeekendMajCondition('min_hours', Number(e.target.value) || 1)
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Heures forfait majorées</Label>
                  <Input
                    type="number"
                    step="0.5"
                    value={weekendMajConditions.flat_hours ?? 1}
                    onChange={(e) =>
                      setWeekendMajCondition('flat_hours', Number(e.target.value) || 1)
                    }
                  />
                </div>
              </>
            )}

            {isAstreinteKm && (
              <>
                <div className="space-y-2">
                  <Label>Franchise km (aller simple)</Label>
                  <Input
                    type="number"
                    min={0}
                    value={astreinteConditions.km_free_threshold_one_way ?? 10}
                    onChange={(e) =>
                      setAstreinteCondition(
                        'km_free_threshold_one_way',
                        Number(e.target.value) || 0,
                      )
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Multiplicateur aller-retour</Label>
                  <Input
                    type="number"
                    min={1}
                    value={astreinteConditions.round_trip_multiplier ?? 2}
                    onChange={(e) =>
                      setAstreinteCondition(
                        'round_trip_multiplier',
                        Number(e.target.value) || 2,
                      )
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Lien astreinte / week-end</Label>
                  <Select
                    value={astreinteConditions.astreinte_link_mode ?? 'same_iso_week'}
                    onValueChange={(v) =>
                      setAstreinteCondition(
                        'astreinte_link_mode',
                        v as AstreinteKmRuleConditions['astreinte_link_mode'],
                      )
                    }
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="same_iso_week">Même semaine ISO</SelectItem>
                      <SelectItem value="month_overlap">Mois (astreinte + WE)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Fréquence de versement</Label>
                  <Select
                    value={astreinteConditions.quantity_mode ?? 'once_if_eligible'}
                    onValueChange={(v) =>
                      setAstreinteCondition(
                        'quantity_mode',
                        v as AstreinteKmRuleConditions['quantity_mode'],
                      )
                    }
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="once_if_eligible">1× par mois si éligible</SelectItem>
                      <SelectItem value="per_qualifying_week">Par semaine qualifiante</SelectItem>
                      <SelectItem value="per_weekend_work_day">Par jour WE travaillé</SelectItem>
                      <SelectItem value="per_manual_trips">Nb trajets (saisie manuelle)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Mode barème</Label>
                  <Select
                    value={astreinteConditions.rate_mode ?? 'coefficient_a'}
                    onValueChange={(v) =>
                      setAstreinteCondition(
                        'rate_mode',
                        v as AstreinteKmRuleConditions['rate_mode'],
                      )
                    }
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="coefficient_a">Coefficient €/km</SelectItem>
                      <SelectItem value="full_bareme">Barème complet a×d+b</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}

            <div className="flex flex-wrap gap-2 sm:col-span-2">
              <Button
                variant="outline"
                disabled={createRule.isPending}
                onClick={() => createRule.mutate()}
              >
                Ajouter la règle
              </Button>
              <Button
                variant="secondary"
                disabled={generate.isPending}
                onClick={() => generate.mutate(true)}
              >
                Simuler le mois
              </Button>
              <Button
                disabled={generate.isPending}
                onClick={() => generate.mutate(false)}
              >
                Générer les saisies
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
