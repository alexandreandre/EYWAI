import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarRange } from 'lucide-react';
import {
  getFractionnementPreview,
  getFractionnementSettings,
  resetFractionnementInputAuto,
  updateFractionnementInput,
  updateFractionnementSettings,
  validateFractionnementGrants,
  type FractionnementSettings,
  type FractionnementSettingsUpdate,
} from '@/api/cpFractionnement';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { queryKeys } from '@/lib/queryKeys';
import { useToast } from '@/hooks/use-toast';

type RowDrafts = Record<
  string,
  { reportJune: string; seniority: string; manualSolde: string }
>;

export default function CpFractionnementSettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [grantYearState, setGrantYearState] = useState(new Date().getFullYear());
  const grantYear = grantYearState;

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.fractionnementSettings(activeCompanyId),
    queryFn: getFractionnementSettings,
    enabled: Boolean(activeCompanyId),
  });

  const previewQuery = useQuery({
    queryKey: queryKeys.fractionnementPreview(activeCompanyId, grantYear),
    queryFn: () => getFractionnementPreview(grantYear),
    enabled: Boolean(activeCompanyId) && Boolean(data?.fractionnement_enabled),
  });

  const [form, setForm] = useState<FractionnementSettings | null>(null);
  const [rowDrafts, setRowDrafts] = useState<RowDrafts>({});
  const [showCalcDetail, setShowCalcDetail] = useState(false);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  useEffect(() => {
    if (!previewQuery.data) return;
    const drafts: RowDrafts = {};
    for (const row of previewQuery.data) {
      drafts[row.employee_id] = {
        reportJune: String(row.cp_reported_june_ouvres ?? 0),
        seniority: String(row.cp_seniority_deduction_ouvres ?? 0),
        manualSolde: String(row.manual_solde_ouvrables ?? 0),
      };
    }
    setRowDrafts(drafts);
  }, [previewQuery.data]);

  const saveSettings = useMutation({
    mutationFn: (payload: FractionnementSettingsUpdate) =>
      updateFractionnementSettings(payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(
        queryKeys.fractionnementSettings(activeCompanyId),
        saved,
      );
      setForm(saved);
      toast({ title: 'Enregistré', description: 'Paramètres fractionnement mis à jour.' });
    },
  });

  const saveRowInput = useMutation({
    mutationFn: ({
      employeeId,
      reportJune,
      seniority,
      manualSolde,
    }: {
      employeeId: string;
      reportJune: number;
      seniority: number;
      manualSolde: number;
    }) =>
      updateFractionnementInput(employeeId, {
        grant_year: grantYear,
        cp_reported_june_ouvres: reportJune,
        cp_seniority_deduction_ouvres: seniority,
        report_june_manual_override: true,
        seniority_manual_override: true,
        manual_solde_ouvrables: manualSolde,
      }),
    onSuccess: () => {
      void previewQuery.refetch();
      toast({ title: 'Enregistré', description: 'Saisies salarié mises à jour.' });
    },
  });

  const resetRowAuto = useMutation({
    mutationFn: (employeeId: string) =>
      resetFractionnementInputAuto(employeeId, grantYear),
    onSuccess: () => {
      void previewQuery.refetch();
      toast({ title: 'Réinitialisé', description: 'Valeurs auto restaurées.' });
    },
  });

  const validateAll = useMutation({
    mutationFn: () => validateFractionnementGrants(grantYear),
    onSuccess: (res) => {
      void previewQuery.refetch();
      toast({
        title: 'Fractionnement validé',
        description: `${res.validated_count} salarié(s).`,
      });
    },
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-56" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  const isManual = form?.calculation_method === 'manual';
  const methodHint =
    form?.calculation_method === 'legal'
      ? 'Reliquat du congé principal au 31/10, calculé depuis les congés posés.'
      : form?.calculation_method === 'manual'
        ? 'Solde en jours ouvrables saisi à la main pour chaque salarié.'
        : 'Formule Mont Blanc Composite : solde CP N-1 au 31/10, moins le report du 1/06 et les CP ancienneté. Le report du 1/06 ne se déduit pas des compteurs : il se saisit ci-dessous.';

  if (isError || !form) {
    return (
      <Card>
        <CardContent className="py-6 text-destructive text-sm">
          Impossible de charger les paramètres fractionnement.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarRange className="h-4 w-4" />
          Fractionnement des congés payés
        </CardTitle>
        <CardDescription>
          {methodHint} Crédit sur la paie de novembre (1 ou 2 jours). 
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <Label htmlFor="frac-enabled">Activer le fractionnement</Label>
          <Switch
            id="frac-enabled"
            disabled={!canEdit}
            checked={form.fractionnement_enabled}
            onCheckedChange={(checked) =>
              setForm({ ...form, fractionnement_enabled: checked })
            }
          />
        </div>

        {form.fractionnement_enabled ? (
          <div className="grid gap-4 sm:grid-cols-3 border-t pt-4">
            <div className="space-y-2">
              <Label>Méthode de calcul</Label>
              <Select
                value={form.calculation_method ?? 'legal'}
                disabled={!canEdit}
                onValueChange={(v) =>
                  setForm({
                    ...form,
                    calculation_method: v as FractionnementSettings['calculation_method'],
                  })
                }
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="legal">Légale (congés posés)</SelectItem>
                  <SelectItem value="mbc">MBC (solde 31/10)</SelectItem>
                  <SelectItem value="manual">Manuelle</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Retrait 5ème semaine (j. ouvrés)</Label>
              <Input
                type="number"
                min={0}
                step="0.5"
                disabled={!canEdit}
                value={form.fifth_week_deduction_ouvres}
                onChange={(e) =>
                  setForm({
                    ...form,
                    fifth_week_deduction_ouvres: Number(e.target.value),
                  })
                }
              />
            </div>
            <div className="space-y-2 sm:col-span-3 flex items-center justify-between gap-4">
              <Label htmlFor="frac-forfait" className="font-normal">
                Exclure les cadres au forfait-jours
              </Label>
              <Switch
                id="frac-forfait"
                disabled={!canEdit}
                checked={form.exclude_forfait_jours ?? true}
                onCheckedChange={(checked) =>
                  setForm({ ...form, exclude_forfait_jours: checked })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Coeff. ouvrés → ouvrables</Label>
              <Input
                type="number"
                min={1}
                step="0.01"
                disabled={!canEdit}
                value={form.ouvres_to_ouvrables_ratio}
                onChange={(e) =>
                  setForm({
                    ...form,
                    ouvres_to_ouvrables_ratio: Number(e.target.value),
                  })
                }
              />
            </div>
          </div>
        ) : null}

        {canEdit ? (
          <Button
            type="button"
            onClick={() => saveSettings.mutate(form)}
            disabled={saveSettings.isPending}
          >
            Enregistrer les paramètres
          </Button>
        ) : null}

        {form.fractionnement_enabled && previewQuery.data && previewQuery.data.length > 0 ? (
          <div className="border-t pt-4 space-y-3 overflow-x-auto">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Label htmlFor="frac-year" className="text-sm">Année</Label>
                <Input
                  id="frac-year"
                  type="number"
                  className="w-24 h-8"
                  value={grantYearState}
                  onChange={(e) => setGrantYearState(Number(e.target.value) || grantYearState)}
                />
                <p className="text-sm font-medium">Prévision au 31/10</p>
              </div>
              <div className="flex items-center gap-2">
                {canEdit ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() =>
                      validateAll.mutate()
                    }
                  >
                    Valider tout
                  </Button>
                ) : null}
                <Switch
                  id="frac-detail"
                  checked={showCalcDetail}
                  onCheckedChange={setShowCalcDetail}
                />
                <Label htmlFor="frac-detail" className="text-xs font-normal text-muted-foreground">
                  Afficher le détail du calcul
                </Label>
              </div>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead className="text-right">CP N-1</TableHead>
                  {isManual ? (
                    <TableHead className="text-right">Solde ouvrables</TableHead>
                  ) : (
                    <>
                      <TableHead className="text-right">Report 1/06</TableHead>
                      <TableHead className="text-right">CP anc.</TableHead>
                    </>
                  )}
                  {showCalcDetail ? (
                    <>
                      <TableHead className="text-right">Solde ouvrés</TableHead>
                      <TableHead className="text-right">Solde ouvrables</TableHead>
                    </>
                  ) : null}
                  <TableHead className="text-right">Jours</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewQuery.data.map((row) => {
                  const draft = rowDrafts[row.employee_id] ?? {
                    reportJune: '0',
                    seniority: '0',
                    manualSolde: '0',
                  };
                  return (
                    <TableRow key={row.employee_id}>
                      <TableCell>
                        {row.last_name} {row.first_name}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {row.solde_cp_n1_ouvres.toFixed(1)}
                      </TableCell>
                      {isManual ? (
                        <TableCell className="text-right">
                          <Input
                            className="h-8 w-20 ml-auto text-right"
                            type="number"
                            min={0}
                            step="0.5"
                            disabled={!canEdit}
                            value={draft.manualSolde}
                            onChange={(e) =>
                              setRowDrafts({
                                ...rowDrafts,
                                [row.employee_id]: {
                                  ...draft,
                                  manualSolde: e.target.value,
                                },
                              })
                            }
                          />
                        </TableCell>
                      ) : (
                        <>
                          <TableCell className="text-right">
                            <Input
                              className="h-8 w-20 ml-auto text-right"
                              type="number"
                              min={0}
                              step="0.5"
                              disabled={!canEdit}
                              value={draft.reportJune}
                              onChange={(e) =>
                                setRowDrafts({
                                  ...rowDrafts,
                                  [row.employee_id]: {
                                    ...draft,
                                    reportJune: e.target.value,
                                  },
                                })
                              }
                            />
                          </TableCell>
                          <TableCell className="text-right">
                            <Input
                              className="h-8 w-20 ml-auto text-right"
                              type="number"
                              min={0}
                              step="0.5"
                              disabled={!canEdit}
                              value={draft.seniority}
                              onChange={(e) =>
                                setRowDrafts({
                                  ...rowDrafts,
                                  [row.employee_id]: {
                                    ...draft,
                                    seniority: e.target.value,
                                  },
                                })
                              }
                            />
                          </TableCell>
                        </>
                      )}
                      {showCalcDetail ? (
                        <>
                          <TableCell className="text-right tabular-nums text-muted-foreground">
                            {row.solde_ouvres.toFixed(1)}
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-muted-foreground">
                            {row.solde_ouvrables.toFixed(1)}
                          </TableCell>
                        </>
                      ) : null}
                      <TableCell className="text-right font-medium tabular-nums">
                        {row.days_granted}
                      </TableCell>
                      <TableCell>
                        {canEdit ? (
                          <div className="flex gap-1">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                saveRowInput.mutate({
                                  employeeId: row.employee_id,
                                  reportJune: Number(draft.reportJune || 0),
                                  seniority: Number(draft.seniority || 0),
                                  manualSolde: Number(draft.manualSolde || 0),
                                })
                              }
                            >
                              OK
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => resetRowAuto.mutate(row.employee_id)}
                            >
                              Auto
                            </Button>
                          </div>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
