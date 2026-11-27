import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Coins, Pencil, Trash2 } from 'lucide-react';
import { getBonusTypes, type BonusType } from '@/api/bonusTypes';
import { getPlanningSettings, getShiftTypes, updatePlanningSettings, type ShiftType } from '@/api/planning';
import {
  applyAstreinteEquipesPreset,
  applyShiftTeamsPayrollPreset,
  createPayrollVariableRule,
  updatePayrollVariableRule,
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
import {
  HeuresParJour,
  PerimetrePointage,
  PlagesDebut,
  ReglageAssiduite,
  ReglageNuit,
} from './ConditionsPointage';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { ChampDecimal } from '@/components/ui/champ-decimal';
import { Switch } from '@/components/ui/switch';
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
import { accord, pluriel } from '@/lib/pluriel';
import { REGLES_SANS_MONTANT, RULE_TYPE_LABELS } from '@/features/company/lib/reglesVariables';
import { conditionsDuType, panierEnMontantFixe } from '@/features/company/lib/conditionsDuType';
import { useEmployeesSummaryQuery } from '@/hooks/queries/useEmployeesQuery';
import { SITUATIONS_REPAS, SITUATION_REPAS_PAR_DEFAUT } from '@/lib/situationsRepas';
import {
  EXCLUSIONS_POINTAGE,
  MODELES_PRIMES_POINTAGE,
  TYPES_POINTAGE,
  erreurDeLaRegle,
  montantIgnore,
  phraseJoursSansHeureDArrivee,
  trierLaSimulation,
} from '@/features/company/lib/primesPointage';

const NOMS_MOIS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];

/** Le mois en cours et les cinq précédents : la paie se génère souvent après la fin du mois. */
function moisProposes(maintenant: Date): { valeur: string; libelle: string }[] {
  return Array.from({ length: 6 }, (_, i) => {
    const d = new Date(maintenant.getFullYear(), maintenant.getMonth() - i, 1);
    return { valeur: `${d.getFullYear()}-${d.getMonth() + 1}`, libelle: `${NOMS_MOIS[d.getMonth()]} ${d.getFullYear()}` };
  });
}

function codeDepuisLibelle(libelle: string): string {
  const base = libelle
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
  return base || 'regle';
}


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
  taux_horaire_inconnu: 'Taux horaire inconnu sur la fiche : prime non calculée',
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
  if (Array.isArray(d.perdue) && d.perdue.length) {
    parts.push(`prime perdue : ${d.perdue.map((p) => `${p.jour.slice(8, 10)}/${p.jour.slice(5, 7)} ${p.motif.replace(/_/g, ' ')}`).join(', ')}`);
  } else if (typeof d.perdue === 'string') {
    parts.push(`prime perdue : ${d.perdue}`);
  }
  if (d.aucun_badge) {
    parts.push(
      "aucun badge sur toute la période : importer son relevé, ou le retirer des salariés de la règle s'il ne badge pas",
    );
  } else if (d.jours_sans_heure_de_debut) {
    parts.push(phraseJoursSansHeureDArrivee(d.jours_sans_heure_de_debut, d.dates_sans_heure_de_debut));
  }
  if (d.jours_repris_de_la_semaine) {
    parts.push(`${d.jours_repris_de_la_semaine} jour(s) sans badge : poste repris des autres jours de la semaine`);
  }
  if (d.prorata_temps_partiel != null) parts.push(`temps partiel ${Math.round(d.prorata_temps_partiel * 100)} %`);
  if (d.km_eligible != null) parts.push(`${d.km_eligible} km`);
  if (d.rate != null) parts.push(`${d.rate} €/km`);
  return parts.join(' · ');
}

function formatPreviewLine(p: PayrollVariablePreviewItem): string {
  const name = [p.first_name, p.last_name].filter(Boolean).join(' ') || p.employee_id;
  const detail = formatPreviewDetail(p);
  const line = `${name} — ${p.rule_label ?? p.rule_code}: ${p.quantity} × ${(p.amount / Math.max(p.quantity, 1)).toFixed(2)} € = ${p.amount.toFixed(2)} €`;
  return detail ? `${line} (${detail})` : line;
}

const LIGNES_MONTREES = 15;

/** Résultat de la simulation ou de la génération : toutes les alertes d'abord, puis les lignes. */
function ResultatDuMois({ result }: { result: PayrollVariableGenerateResult }) {
  const { alertes, lignes } = trierLaSimulation(result);
  return (
    <div className="rounded-lg border bg-muted/40 p-3 text-sm space-y-2" data-testid="resultat-variables">
      <p className="font-medium">
        {result.dry_run ? 'Simulation' : 'Saisies générées'} {result.month}/{result.year} — {pluriel(lignes.length, 'ligne')}
        {result.dry_run ? '' : `, ${pluriel(result.written_count, 'écriture')}`}
      </p>
      {alertes.length > 0 && (
        <div className="rounded border border-amber-200 bg-amber-50 p-2 text-amber-900" data-testid="alertes-variables">
          <p className="font-medium">À vérifier ({alertes.length})</p>
          <ul className="list-disc pl-5">
            {alertes.map((p, i) => (
              <li key={`${p.employee_id}-${p.rule_code}-${i}`}>{formatPreviewLine(p)}</li>
            ))}
          </ul>
        </div>
      )}
      {lignes.length === 0 && alertes.length === 0 && <p>Aucune ligne.</p>}
      <div className="whitespace-pre-wrap">{lignes.slice(0, LIGNES_MONTREES).map(formatPreviewLine).join('\n')}</div>
      {lignes.length > LIGNES_MONTREES && (
        <p className="text-muted-foreground">… et {lignes.length - LIGNES_MONTREES} {accord(lignes.length - LIGNES_MONTREES, 'autre')}</p>
      )}
    </div>
  );
}

export default function PayrollVariableRulesCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const now = new Date();
  const [moisChoisi, setMoisChoisi] = useState(() => moisProposes(new Date())[0].valeur);
  const { data: salaries = [] } = useEmployeesSummaryQuery('active');

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
    amount: null,
    enabled: true,
    generation_mode: 'auto',
    conditions: {},
    sort_order: 0,
  });

  const [simulation, setSimulation] = useState<PayrollVariableGenerateResult | null>(null);
  // Règle en cours de modification (même formulaire, prérempli).
  const [enModification, setEnModification] = useState<PayrollVariableRule | null>(null);
  const salariesCibles = (draft.conditions?.employee_ids as string[] | undefined) ?? null;
  const basculerSalarie = (id: string, coche: boolean) => {
    const actuels = salariesCibles ?? [];
    const suivants = coche ? [...new Set([...actuels, id])] : actuels.filter((x) => x !== id);
    setDraft({ ...draft, conditions: { ...draft.conditions, employee_ids: suivants } });
  };
  const selectedShiftCodes = (draft.conditions?.shift_type_codes as string[] | undefined) ?? [];
  const isAstreinteKm = draft.rule_type === 'per_astreinte_weekend_km';
  const isTiered = draft.rule_type === 'per_astreinte_week_tiered';
  const isWeekendMaj = draft.rule_type === 'per_astreinte_weekend_majoration';
  const isPresenceWeek = draft.rule_type === 'per_week_without_absence';
  const noAmountRule = REGLES_SANS_MONTANT.has(draft.rule_type);
  const astreinteConditions = (draft.conditions ?? {}) as AstreinteKmRuleConditions;
  const tieredConditions = (draft.conditions ?? {}) as AstreinteWeekTieredConditions;
  const weekendMajConditions = (draft.conditions ?? {}) as AstreinteWeekendMajorationConditions;
  const presenceConditions = (draft.conditions ?? {}) as PresenceWeekRuleConditions;
  const selectedAbsenceTypes = presenceConditions.absence_types ?? [];

  const hasNightHourRule = rules.some((r) => r.rule_type === 'per_night_hour' && r.enabled);

  // « Martine prépare ces primes à chaque bulletin » : le réglage vivait dans la
  // carte Planning équipes, que l'équipe n'ouvre pas ; sans lui, une génération
  // oubliée laissait les bulletins sans paniers, sans rien dire (examen du 20/11).
  const { data: planningSettings } = useQuery({
    queryKey: queryKeys.planningSettings(activeCompanyId),
    queryFn: getPlanningSettings,
    enabled: Boolean(activeCompanyId),
  });
  const autoAvantBulletin = Boolean(planningSettings?.auto_generate_payroll_variables_before_payslip);
  const reglerAuto = useMutation({
    mutationFn: (actif: boolean) => updatePlanningSettings({ auto_generate_payroll_variables_before_payslip: actif }),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.planningSettings(activeCompanyId), saved);
      toast({
        title: saved.auto_generate_payroll_variables_before_payslip
          ? 'Les primes seront préparées à chaque bulletin'
          : 'Préparation automatique coupée',
      });
    },
    onError: (err: Error) => toast({ title: 'Erreur', description: err.message, variant: 'destructive' }),
  });
  const reglesActives = rules.some((r) => r.enabled && r.generation_mode === 'auto');
  const commencerDepuisModele = (regle: Partial<PayrollVariableRule>) => {
    setEnModification(null);
    setSimulation(null);
    setDraft({
      code: '',
      enabled: true,
      generation_mode: 'auto',
      sort_order: 0,
      ...regle,
      conditions: { ...(regle.conditions ?? {}) },
    });
  };

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
      const erreur = erreurDeLaRegle(draft, rules, enModification?.id);
      if (erreur) throw new Error(erreur);
      if (isPresenceWeek && !presenceConditions.periode_assiduite && selectedAbsenceTypes.length === 0) {
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
      if (Array.isArray(draft.conditions?.employee_ids)) {
        if ((draft.conditions?.employee_ids as string[]).length === 0) {
          throw new Error('Cochez au moins un salarié, ou choisissez « Tous les salariés ».');
        }
        conditions = { ...conditions, employee_ids: draft.conditions?.employee_ids };
      }
      if (/panier|repas/i.test(draft.label ?? '')) {
        conditions = {
          ...conditions,
          situation_repas: draft.conditions?.situation_repas ?? SITUATION_REPAS_PAR_DEFAUT,
        };
      }
      const ruleAmount = noAmountRule
        ? null
        : isPresenceWeek
          ? Number(draft.amount ?? presenceConditions.amount_per_week ?? 0)
          : montantIgnore(draft)
            ? null
            : (draft.amount ?? 0);
      const regle = {
        code: draft.code || codeDepuisLibelle(draft.label || ''),
        label: draft.label || 'Nouvelle règle',
        enabled: true,
        rule_type: draft.rule_type || 'fixed_monthly',
        amount: ruleAmount,
        bonus_type_id: draft.bonus_type_id ?? null,
        conditions,
        generation_mode:
          draft.generation_mode
          || (noAmountRule ? 'suggest' : 'auto'),
        sort_order: enModification?.sort_order ?? rules.length,
      };
      return enModification?.id
        ? updatePayrollVariableRule(enModification.id, { ...regle, enabled: enModification.enabled })
        : createPayrollVariableRule(regle);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.payrollVariableRules(activeCompanyId),
      });
      toast({ title: enModification ? 'Règle modifiée' : 'Règle créée' });
      setEnModification(null);
      setDraft({
        code: '',
        label: '',
        rule_type: 'fixed_monthly',
        amount: null,
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
      generatePayrollVariables(
        Number(moisChoisi.split('-')[0]),
        Number(moisChoisi.split('-')[1]),
        dryRun,
      ),
    onSuccess: (result) => {
      setSimulation(result);
      toast({
        title: result.dry_run ? 'Simulation terminée' : 'Variables générées',
        description: `${pluriel(result.preview.length, 'ligne')} — ${pluriel(result.written_count, 'écriture')}`,
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
        description: `${pluriel(result.created_rules.length, 'règle')}, ${pluriel(result.created_bonus_types.length, 'type')} de prime ${accord(result.created_bonus_types.length, 'créé')}.`,
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
        description: `${pluriel(result.created_rules.length, 'règle')}, ${pluriel(result.created_bonus_types.length, 'type')} de prime ${accord(result.created_bonus_types.length, 'créé')}. Complétez les montants et codes export.`,
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
              Une règle « heures de nuit » est active : ne réglez pas en plus une majoration de nuit
              sur les types de poste du planning, sinon la nuit serait payée deux fois.
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
                <TableHead>Salariés</TableHead>
                <TableHead>Mode</TableHead>
                {canEdit && <TableHead className="w-24" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.code}</TableCell>
                  <TableCell>{r.label}</TableCell>
                  <TableCell>{RULE_TYPE_LABELS[r.rule_type] ?? r.rule_type}</TableCell>
                  <TableCell>{r.amount ?? '—'}</TableCell>
                  <TableCell>
                    {Array.isArray(r.conditions?.employee_ids)
                      ? pluriel((r.conditions?.employee_ids as string[]).length, 'salarié')
                      : 'Tous'}
                  </TableCell>
                  <TableCell>{GENERATION_MODE_LABELS[r.generation_mode] ?? r.generation_mode}</TableCell>
                  {canEdit && r.id && (
                    <TableCell className="whitespace-nowrap">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Modifier la règle"
                        onClick={() => {
                          setEnModification(r);
                          setDraft({ ...r, conditions: { ...(r.conditions ?? {}) } });
                        }}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
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
                  <TableCell colSpan={canEdit ? 7 : 6} className="text-muted-foreground">
                    Aucune règle configurée.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}

        {simulation && <ResultatDuMois result={simulation} />}

        {canEdit && (
          <div className="rounded-lg border p-3 space-y-2" data-testid="preparation-auto">
            <div className="flex items-center gap-3">
              <Switch
                id="primes-auto"
                checked={autoAvantBulletin}
                disabled={!planningSettings || reglerAuto.isPending}
                onCheckedChange={(v) => reglerAuto.mutate(Boolean(v))}
              />
              <Label htmlFor="primes-auto" className="cursor-pointer">
                Martine prépare ces primes à chaque calcul de bulletin
              </Label>
            </div>
            {planningSettings && !autoAvantBulletin && reglesActives && (
              <p className="text-sm text-amber-800" data-testid="preparation-auto-coupee">
                Coupé : les primes ne sortent sur les bulletins qu&apos;après « Générer les saisies » du mois.
                Activez-le pour ne pas l&apos;oublier.
              </p>
            )}
          </div>
        )}

        {canEdit && (
          <div className="space-y-2" data-testid="modeles-primes">
            <p className="text-sm font-medium">Nouvelle prime liée aux pointages</p>
            <div className="flex flex-wrap gap-2">
              {MODELES_PRIMES_POINTAGE.map((m) => (
                <Button
                  key={m.id}
                  type="button"
                  variant="outline"
                  size="sm"
                  title={m.aide}
                  onClick={() => commencerDepuisModele(m.regle)}
                >
                  {m.titre}
                </Button>
              ))}
            </div>
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
                  // Les conditions d'un autre type partent ; les salariés
                  // choisis restent (Lyon, 17/11).
                  const communes = conditionsDuType(rt, draft.conditions);
                  let conditions = communes;
                  let generation_mode = draft.generation_mode;
                  let amount = draft.amount;
                  if (rt === 'per_astreinte_weekend_km') {
                    conditions = { ...communes, ...DEFAULT_ASTREINTE_KM_CONDITIONS };
                    generation_mode = 'suggest';
                    amount = null;
                  } else if (rt === 'per_astreinte_week_tiered') {
                    conditions = { ...communes, ...DEFAULT_ASTREINTE_TIERED };
                    generation_mode = 'suggest';
                    amount = null;
                  } else if (rt === 'per_astreinte_weekend_majoration') {
                    conditions = { ...communes, ...DEFAULT_ASTREINTE_WEEKEND_MAJ };
                    generation_mode = 'suggest';
                    amount = null;
                  } else if (rt === 'transport_domicile_travail') {
                    // Le montant vient de la fiche de chaque bénéficiaire.
                    conditions = communes;
                    amount = null;
                  } else if (rt === 'per_week_without_absence') {
                    // Pas de montant d'office : 6 € (LEWIS) versés par mois chez
                    // Mont Blanc si on l'oubliait (examen du 20/11).
                    conditions = { ...communes, periode_assiduite: 'semaine', absence_types: [] };
                    generation_mode = 'auto';
                    amount = null;
                  }
                  if (!enModification && TYPES_POINTAGE.has(rt)) {
                    conditions = { ...EXCLUSIONS_POINTAGE, ...conditions };
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
              {panierEnMontantFixe(draft.label, draft.rule_type) && (
                <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1" data-testid="panier-montant-fixe">
                  Un panier s'exonère par repas : en montant fixe mensuel, Martine n'y voit qu'un seul
                  panier (15 € donnent 7,50 € exonérés et 7,50 € cotisés). Choisissez plutôt{' '}
                  <button
                    type="button"
                    className="underline font-medium"
                    onClick={() =>
                      setDraft({
                        ...draft,
                        rule_type: 'per_worked_day',
                        conditions: conditionsDuType('per_worked_day', draft.conditions),
                      })
                    }
                  >
                    « Par jour travaillé (calendrier) »
                  </button>{' '}
                  (montant par panier × jours travaillés), ou une saisie du mois « montant par panier ×
                  nombre de paniers ».
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label>
                {draft.rule_type === 'transport_domicile_travail'
                  ? 'Montant (celui de la fiche de chaque salarié)'
                  : noAmountRule
                  ? 'Montant (calculé auto)'
                  : isPresenceWeek
                    ? presenceConditions.periode_assiduite === 'mois'
                      ? 'Montant mensuel à temps plein (€)'
                      : 'Montant hebdomadaire (€)'
                    : draft.rule_type === 'per_night_hour'
                      ? 'Montant par heure de nuit (€)'
                      : 'Montant unitaire (€)'}
              </Label>
              <ChampDecimal
                disabled={noAmountRule || Boolean(montantIgnore(draft))}
                value={noAmountRule || montantIgnore(draft) ? null : draft.amount}
                placeholder={
                  draft.rule_type === 'transport_domicile_travail'
                    ? 'Indemnité de trajet de la fiche'
                    : noAmountRule
                      ? 'Voir conditions ci-dessous'
                      : undefined
                }
                onValueChange={(v) => setDraft({ ...draft, amount: v })}
              />
              {montantIgnore(draft) && <p className="text-xs text-muted-foreground">{montantIgnore(draft)}</p>}
            </div>
            <details className="sm:col-span-2 rounded-md border px-3 py-2" data-testid="options-avancees">
              <summary className="cursor-pointer text-sm text-muted-foreground">
                Options avancées (code, type de prime du catalogue, code export, mode) : à laisser telles quelles
              </summary>
              <div className="grid gap-3 pt-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Code</Label>
              <Input
                value={draft.code ?? ''}
                onChange={(e) => setDraft({ ...draft, code: e.target.value })}
                placeholder="panier_poste"
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
              <Label>Code export paie (facultatif)</Label>
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
              <p className="text-xs text-muted-foreground">
                À laisser vide. C&apos;est le code de la rubrique dans un autre logiciel de paie ; rempli, il
                s&apos;imprime entre parenthèses après le libellé sur le bulletin et ne sert à aucun export.
              </p>
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
              </div>
            </details>

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

            {isPresenceWeek && presenceConditions.periode_assiduite && (
              <div className="sm:col-span-2">
                <ReglageAssiduite
                  conditions={draft.conditions ?? {}}
                  onChange={(conditions) => setDraft({ ...draft, conditions })}
                />
              </div>
            )}

            {isPresenceWeek && (!presenceConditions.periode_assiduite || selectedAbsenceTypes.length > 0) && (
              <div className="space-y-3 sm:col-span-2">
                <Label>
                  {presenceConditions.periode_assiduite
                    ? 'Demandes d’absence qui font aussi perdre la prime (facultatif)'
                    : 'Types d’absence qui annulent la prime (semaine ISO)'}
                </Label>
                <p className="text-xs text-muted-foreground">
                  {presenceConditions.periode_assiduite
                    ? 'Le calendrier suffit ; cochez ici les demandes d’absence à surveiller en plus.'
                    : 'Cochez explicitement les absences à surveiller — aucune sélection = règle inactive.'}
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
                  <ChampDecimal
                    value={tieredConditions.amount_normal ?? 176.18}
                    onValueChange={(v) => setTieredCondition('amount_normal', v ?? 0)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Prime semaine Noël (€)</Label>
                  <ChampDecimal
                    value={tieredConditions.amount_christmas ?? 352.36}
                    onValueChange={(v) => setTieredCondition('amount_christmas', v ?? 0)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Prime pont (€)</Label>
                  <ChampDecimal
                    value={tieredConditions.amount_bridge ?? 250}
                    onValueChange={(v) => setTieredCondition('amount_bridge', v ?? 0)}
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
                  <ChampDecimal
                    value={weekendMajConditions.weekday_rates?.['5'] ?? 0.25}
                    onValueChange={(v) =>
                      setWeekendMajCondition('weekday_rates', {
                        ...weekendMajConditions.weekday_rates,
                        '5': v ?? 0,
                        '6': weekendMajConditions.weekday_rates?.['6'] ?? 1,
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Majoration dimanche (1 = 100 %)</Label>
                  <ChampDecimal
                    value={weekendMajConditions.weekday_rates?.['6'] ?? 1}
                    onValueChange={(v) =>
                      setWeekendMajCondition('weekday_rates', {
                        ...weekendMajConditions.weekday_rates,
                        '5': weekendMajConditions.weekday_rates?.['5'] ?? 0.25,
                        '6': v ?? 0,
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Heures minimum pointées</Label>
                  <ChampDecimal
                    value={weekendMajConditions.min_hours ?? 1}
                    onValueChange={(v) => setWeekendMajCondition('min_hours', v || 1)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Heures forfait majorées</Label>
                  <ChampDecimal
                    value={weekendMajConditions.flat_hours ?? 1}
                    onValueChange={(v) => setWeekendMajCondition('flat_hours', v || 1)}
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

            {draft.rule_type === 'per_worked_day' && (
              <div className="space-y-2 sm:col-span-2" data-testid="regle-jour-travaille">
                <p className="text-sm text-muted-foreground">
                  Martine compte les jours travaillés du calendrier de chaque salarié sur le mois de paie
                  (heures réelles, ou heures prévues sans absence), puis pose « montant × jours » dans
                  Primes. Pour un panier, le nombre de paniers suit : chaque panier est exonéré jusqu&apos;au
                  plafond de l&apos;Urssaf.
                </p>
                <Label htmlFor="min_heures">Seulement les jours d&apos;au moins (heures, facultatif)</Label>
                <ChampDecimal
                  id="min_heures"
                  className="max-w-[10rem]"
                  placeholder="ex. 6"
                  value={draft.conditions?.min_heures as number | undefined}
                  onValueChange={(v) =>
                    setDraft({
                      ...draft,
                      conditions: {
                        ...draft.conditions,
                        min_heures: v ?? undefined,
                      },
                    })
                  }
                />
                <PlagesDebut
                  conditions={draft.conditions ?? {}}
                  onChange={(conditions) => setDraft({ ...draft, conditions })}
                />
                <HeuresParJour
                  conditions={draft.conditions ?? {}}
                  onChange={(conditions) => setDraft({ ...draft, conditions })}
                />
              </div>
            )}

            {draft.rule_type === 'per_night_hour' && (
              <div className="sm:col-span-2">
                <ReglageNuit
                  conditions={draft.conditions ?? {}}
                  onChange={(conditions) => setDraft({ ...draft, conditions })}
                />
              </div>
            )}

            {['per_worked_day', 'per_week_without_absence', 'per_night_hour'].includes(draft.rule_type ?? '') && (
              <div className="sm:col-span-2">
                <PerimetrePointage
                  conditions={draft.conditions ?? {}}
                  onChange={(conditions) => setDraft({ ...draft, conditions })}
                />
              </div>
            )}

            {/panier|repas/i.test(draft.label ?? '') && (
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="regle-situation-repas">Où le salarié prend son repas</Label>
                <select
                  id="regle-situation-repas"
                  data-testid="regle-situation-repas"
                  className="block h-10 w-full max-w-md rounded-md border bg-background px-3 text-sm"
                  value={(draft.conditions?.situation_repas as string | undefined) ?? SITUATION_REPAS_PAR_DEFAUT}
                  onChange={(e) =>
                    setDraft({ ...draft, conditions: { ...draft.conditions, situation_repas: e.target.value } })
                  }
                >
                  {SITUATIONS_REPAS.map((s) => (
                    <option key={s.valeur} value={s.valeur}>{s.libelle}</option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">
                  Au-delà de ce plafond par panier, Martine ajoute seule la ligne « Réintégration panier », soumise à cotisations.
                </p>
              </div>
            )}

            {draft.rule_type !== 'transport_domicile_travail' && (
              <div className="space-y-2 sm:col-span-2" data-testid="regle-salaries">
                <Label>Salariés concernés</Label>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="regle-tous"
                    checked={salariesCibles === null}
                    onCheckedChange={(v) => {
                      const conditions = { ...(draft.conditions ?? {}) } as Record<string, unknown>;
                      if (v) delete conditions.employee_ids;
                      else conditions.employee_ids = [];
                      setDraft({ ...draft, conditions });
                    }}
                  />
                  <Label htmlFor="regle-tous" className="cursor-pointer font-normal">
                    Tous les salariés de la société
                  </Label>
                </div>
                {salariesCibles !== null && (
                  <div className="max-h-56 overflow-y-auto rounded-md border p-2 grid gap-1 sm:grid-cols-2">
                    {salaries.map((s) => (
                      <label key={s.id} className="flex items-center gap-2 text-sm cursor-pointer">
                        <Checkbox
                          checked={salariesCibles.includes(s.id)}
                          onCheckedChange={(v) => basculerSalarie(s.id, Boolean(v))}
                        />
                        {s.last_name} {s.first_name}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="space-y-2 sm:col-span-2">
              <Label>Mois à simuler ou à générer</Label>
              <Select value={moisChoisi} onValueChange={setMoisChoisi}>
                <SelectTrigger className="max-w-[14rem]" data-testid="regle-mois"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {moisProposes(now).map((m) => (
                    <SelectItem key={m.valeur} value={m.valeur}>{m.libelle}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-wrap gap-2 sm:col-span-2">
              <Button
                variant="outline"
                disabled={createRule.isPending}
                onClick={() => createRule.mutate()}
              >
                {enModification ? 'Enregistrer' : 'Ajouter la règle'}
              </Button>
              {enModification && (
                <Button
                  variant="ghost"
                  onClick={() => {
                    setEnModification(null);
                    setDraft({
                      code: '',
                      label: '',
                      rule_type: 'fixed_monthly',
                      amount: null,
                      enabled: true,
                      generation_mode: 'auto',
                      conditions: {},
                      sort_order: 0,
                    });
                  }}
                >
                  Annuler la modification
                </Button>
              )}
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
