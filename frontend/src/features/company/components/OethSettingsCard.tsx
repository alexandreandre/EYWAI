import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  computeOethAnnualReview,
  getOethAnnualReview,
  getOethCompliance,
  getOethSettings,
  saveOethDeductions,
  saveOethEcapPositions,
  saveOethExternes,
  saveOethSettings,
  saveUrssafOverride,
  OETH_DEDUCTION_TYPE_OPTIONS,
  OETH_EXTERNAL_TYPE_OPTIONS,
  type BoethExterne,
  type OethDeduction,
  type OethEcapPosition,
  type OethSettings,
  type OethSettingsUpdate,
} from '@/api/oethSettings';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';
import { Accessibility, AlertTriangle, Calculator, Plus, Trash2 } from 'lucide-react';

function toUpdatePayload(form: OethSettings): OethSettingsUpdate {
  return {
    oeth_assujetti_override: form.oeth_assujetti_override,
    date_franchissement_seuil_20: form.date_franchissement_seuil_20,
    accord_agree_code: form.accord_agree_code,
    accord_agree_valid_from: form.accord_agree_valid_from,
    accord_agree_valid_to: form.accord_agree_valid_to,
    declaring_establishment_siret: form.declaring_establishment_siret,
    departement: form.departement,
    taux_obligation: form.taux_obligation,
  };
}

function formatEur(value: number | null | undefined): string {
  if (value == null) return '—';
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(value);
}

function emptyExterne(): BoethExterne {
  return {
    external_type: '01',
    annual_average_count: 0,
    amount_ht: 0,
    contract_reference: '',
  };
}

function emptyDeduction(): OethDeduction {
  return {
    deduction_type: '061',
    amount_eur: 0,
    provider_name: '',
    reference: '',
  };
}

function emptyEcapPosition(): OethEcapPosition {
  return {
    job_code_pcs_ese: '',
    annual_average_count: 0,
  };
}

export default function OethSettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const reviewYear = new Date().getFullYear() - 1;

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh';
  }, [user?.role]);

  const { data: settings, isLoading } = useQuery({
    queryKey: ['oeth-settings', activeCompanyId],
    queryFn: getOethSettings,
    enabled: Boolean(activeCompanyId),
  });

  const { data: compliance } = useQuery({
    queryKey: ['oeth-compliance', activeCompanyId],
    queryFn: getOethCompliance,
    enabled: Boolean(activeCompanyId),
  });

  const { data: review, isLoading: reviewLoading } = useQuery({
    queryKey: ['oeth-annual-review', activeCompanyId, reviewYear],
    queryFn: () => getOethAnnualReview(reviewYear),
    enabled: Boolean(activeCompanyId),
  });

  const [form, setForm] = useState<OethSettings | null>(null);
  const [urssafEma, setUrssafEma] = useState({
    assujettissement: '',
    boeth: '',
    ecap: '',
  });
  const [externes, setExternes] = useState<BoethExterne[]>([]);
  const [deductions, setDeductions] = useState<OethDeduction[]>([]);
  const [ecapPositions, setEcapPositions] = useState<OethEcapPosition[]>([]);

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  useEffect(() => {
    if (review) {
      setUrssafEma({
        assujettissement: review.urssaf_ema_assujettissement?.toString() ?? '',
        boeth: review.urssaf_ema_boeth?.toString() ?? '',
        ecap: review.urssaf_ema_ecap?.toString() ?? '',
      });
      setExternes(review.externes?.length ? review.externes : []);
      setDeductions(review.deductions?.length ? review.deductions : []);
      setEcapPositions(review.ecap_positions?.length ? review.ecap_positions : []);
    }
  }, [review]);

  const saveSettingsMutation = useMutation({
    mutationFn: () => saveOethSettings(toUpdatePayload(form!)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oeth-settings'] });
      queryClient.invalidateQueries({ queryKey: ['oeth-compliance'] });
      toast({ title: 'Paramètres OETH enregistrés' });
    },
  });

  const computeMutation = useMutation({
    mutationFn: () => computeOethAnnualReview(reviewYear),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oeth-annual-review'] });
      toast({ title: 'Calcul DOETH actualisé' });
    },
  });

  const urssafMutation = useMutation({
    mutationFn: () =>
      saveUrssafOverride(reviewYear, {
        urssaf_ema_assujettissement: urssafEma.assujettissement
          ? parseFloat(urssafEma.assujettissement)
          : null,
        urssaf_ema_boeth: urssafEma.boeth ? parseFloat(urssafEma.boeth) : null,
        urssaf_ema_ecap: urssafEma.ecap ? parseFloat(urssafEma.ecap) : null,
        urssaf_notified_at: new Date().toISOString().slice(0, 10),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oeth-annual-review'] });
      toast({ title: 'EMA URSSAF enregistrés' });
    },
  });

  const externesMutation = useMutation({
    mutationFn: () => saveOethExternes(reviewYear, externes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oeth-annual-review'] });
      toast({ title: 'Emplois BOETH externes enregistrés' });
    },
    onError: () => {
      toast({ title: 'Erreur', description: 'Enregistrement des externes impossible.', variant: 'destructive' });
    },
  });

  const deductionsMutation = useMutation({
    mutationFn: () => saveOethDeductions(reviewYear, deductions),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oeth-annual-review'] });
      toast({ title: 'Déductions OETH enregistrées' });
    },
    onError: () => {
      toast({ title: 'Erreur', description: 'Enregistrement des déductions impossible.', variant: 'destructive' });
    },
  });

  const ecapMutation = useMutation({
    mutationFn: () => saveOethEcapPositions(reviewYear, ecapPositions),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oeth-annual-review'] });
      toast({ title: 'Postes ECAP enregistrés' });
    },
  });

  if (isLoading || !form) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center text-base">
            <Accessibility className="mr-2 h-5 w-5 text-primary" />
            OETH — Obligation d&apos;emploi TH
          </CardTitle>
          <CardDescription>
            Suivi du taux de 6 % et paramétrage de la déclaration annuelle (DOETH).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {compliance ? (
            <div className="flex flex-wrap gap-2">
              <Badge variant={compliance.oeth_assujetti ? 'default' : 'secondary'}>
                {compliance.oeth_assujetti ? 'Assujetti OETH' : 'Non assujetti (< 20 sal.)'}
              </Badge>
              <Badge variant="outline">{compliance.boeth_count} BOETH internes</Badge>
              <Badge variant="outline">Taux {compliance.taux_emploi_pct.toFixed(1)} %</Badge>
              {compliance.boeth_manquants > 0 ? (
                <Badge variant="destructive">{compliance.boeth_manquants} manquant(s)</Badge>
              ) : null}
              {compliance.neutralisation_active ? (
                <Badge variant="secondary">Neutralisation active</Badge>
              ) : null}
            </div>
          ) : null}

          {compliance?.alertes?.length ? (
            <Alert className="border-amber-200 bg-amber-50/80">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              <AlertDescription>
                <ul className="list-inside list-disc text-sm">
                  {compliance.alertes.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          ) : null}

          {canEdit ? (
            <div className="grid gap-4 md:grid-cols-2">
              <div className="flex items-center justify-between gap-4 rounded-lg border p-3">
                <div>
                  <Label>Forcer assujettissement OETH</Label>
                  <p className="text-xs text-muted-foreground">
                    Effectif actuel : {form.effectif_actif ?? '—'} salariés
                  </p>
                </div>
                <Switch
                  checked={form.oeth_assujetti_override ?? form.oeth_assujetti}
                  onCheckedChange={(v) =>
                    setForm((f) => f && { ...f, oeth_assujetti_override: v })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Date franchissement 20 salariés</Label>
                <Input
                  type="date"
                  value={form.date_franchissement_seuil_20 ?? ''}
                  onChange={(e) =>
                    setForm((f) =>
                      f ? { ...f, date_franchissement_seuil_20: e.target.value || null } : f,
                    )
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Code accord agréé (AAETH)</Label>
                <Input
                  value={form.accord_agree_code ?? ''}
                  onChange={(e) =>
                    setForm((f) => f && { ...f, accord_agree_code: e.target.value || null })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>SIRET établissement déclarant DSN</Label>
                <Input
                  value={form.declaring_establishment_siret ?? ''}
                  onChange={(e) =>
                    setForm((f) =>
                      f ? { ...f, declaring_establishment_siret: e.target.value || null } : f,
                    )
                  }
                />
              </div>
            </div>
          ) : null}

          {canEdit ? (
            <Button onClick={() => saveSettingsMutation.mutate()} disabled={saveSettingsMutation.isPending}>
              Enregistrer les paramètres
            </Button>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center text-base">
            <Calculator className="mr-2 h-5 w-5" />
            Assistant DOETH {reviewYear}
          </CardTitle>
          <CardDescription>
            Calcul automatique de la contribution Agefiph — déclaration dans la DSN d&apos;avril{' '}
            {reviewYear + 1}.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {reviewLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : review ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <p className="text-xs text-muted-foreground">EMA assujettissement</p>
                  <p className="font-semibold tabular-nums">{review.ema_assujettissement ?? '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">EMA BOETH interne</p>
                  <p className="font-semibold tabular-nums">{review.ema_boeth_interne ?? '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Quota 6 %</p>
                  <p className="font-semibold tabular-nums">{review.quota_boeth ?? '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Contribution due</p>
                  <p className="font-semibold tabular-nums">{formatEur(review.contribution_due)}</p>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-3 text-sm">
                <p>Brute : {formatEur(review.contribution_brute)}</p>
                <p>Nette : {formatEur(review.contribution_nette)}</p>
                <p>Taux emploi : {review.taux_emploi_pct ?? '—'} %</p>
              </div>

              {canEdit ? (
                <>
                  <div className="rounded-lg border p-4 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">Emplois BOETH externes</p>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setExternes((rows) => [...rows, emptyExterne()])}
                      >
                        <Plus className="mr-1 h-4 w-4" />
                        Ajouter
                      </Button>
                    </div>
                    {externes.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Aucun emploi externe saisi.</p>
                    ) : (
                      <div className="space-y-2">
                        {externes.map((row, index) => (
                          <div key={index} className="grid gap-2 sm:grid-cols-5 items-end">
                            <div className="space-y-1 sm:col-span-2">
                              <Label className="text-xs">Type</Label>
                              <select
                                className="flex h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                                value={row.external_type}
                                onChange={(e) =>
                                  setExternes((rows) =>
                                    rows.map((r, i) =>
                                      i === index ? { ...r, external_type: e.target.value } : r,
                                    ),
                                  )
                                }
                              >
                                {OETH_EXTERNAL_TYPE_OPTIONS.map((opt) => (
                                  <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div className="space-y-1">
                              <Label className="text-xs">EMA</Label>
                              <Input
                                type="number"
                                min={0}
                                step="0.01"
                                value={row.annual_average_count}
                                onChange={(e) =>
                                  setExternes((rows) =>
                                    rows.map((r, i) =>
                                      i === index
                                        ? { ...r, annual_average_count: parseFloat(e.target.value) || 0 }
                                        : r,
                                    ),
                                  )
                                }
                              />
                            </div>
                            <div className="space-y-1">
                              <Label className="text-xs">Montant HT</Label>
                              <Input
                                type="number"
                                min={0}
                                step="0.01"
                                value={row.amount_ht}
                                onChange={(e) =>
                                  setExternes((rows) =>
                                    rows.map((r, i) =>
                                      i === index
                                        ? { ...r, amount_ht: parseFloat(e.target.value) || 0 }
                                        : r,
                                    ),
                                  )
                                }
                              />
                            </div>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={() => setExternes((rows) => rows.filter((_, i) => i !== index))}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => externesMutation.mutate()}
                      disabled={externesMutation.isPending}
                    >
                      Enregistrer les externes
                    </Button>
                  </div>

                  <div className="rounded-lg border p-4 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">Déductions OETH</p>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setDeductions((rows) => [...rows, emptyDeduction()])}
                      >
                        <Plus className="mr-1 h-4 w-4" />
                        Ajouter
                      </Button>
                    </div>
                    {deductions.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Aucune déduction saisie.</p>
                    ) : (
                      <div className="space-y-2">
                        {deductions.map((row, index) => (
                          <div key={index} className="grid gap-2 sm:grid-cols-4 items-end">
                            <div className="space-y-1">
                              <Label className="text-xs">Type</Label>
                              <select
                                className="flex h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                                value={row.deduction_type}
                                onChange={(e) =>
                                  setDeductions((rows) =>
                                    rows.map((r, i) =>
                                      i === index ? { ...r, deduction_type: e.target.value } : r,
                                    ),
                                  )
                                }
                              >
                                {OETH_DEDUCTION_TYPE_OPTIONS.map((opt) => (
                                  <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div className="space-y-1">
                              <Label className="text-xs">Montant €</Label>
                              <Input
                                type="number"
                                min={0}
                                step="0.01"
                                value={row.amount_eur}
                                onChange={(e) =>
                                  setDeductions((rows) =>
                                    rows.map((r, i) =>
                                      i === index
                                        ? { ...r, amount_eur: parseFloat(e.target.value) || 0 }
                                        : r,
                                    ),
                                  )
                                }
                              />
                            </div>
                            <div className="space-y-1">
                              <Label className="text-xs">Prestataire</Label>
                              <Input
                                value={row.provider_name ?? ''}
                                onChange={(e) =>
                                  setDeductions((rows) =>
                                    rows.map((r, i) =>
                                      i === index ? { ...r, provider_name: e.target.value } : r,
                                    ),
                                  )
                                }
                              />
                            </div>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={() => setDeductions((rows) => rows.filter((_, i) => i !== index))}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => deductionsMutation.mutate()}
                      disabled={deductionsMutation.isPending}
                    >
                      Enregistrer les déductions
                    </Button>
                  </div>

                  <div className="rounded-lg border p-4 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">Postes ECAP (PCS-ESE)</p>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setEcapPositions((rows) => [...rows, emptyEcapPosition()])}
                      >
                        <Plus className="mr-1 h-4 w-4" />
                        Ajouter
                      </Button>
                    </div>
                    {ecapPositions.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Aucun poste ECAP saisi.</p>
                    ) : (
                      <div className="space-y-2">
                        {ecapPositions.map((row, index) => (
                          <div key={index} className="grid gap-2 sm:grid-cols-3 items-end">
                            <div className="space-y-1 sm:col-span-2">
                              <Label className="text-xs">Code PCS-ESE</Label>
                              <Input
                                value={row.job_code_pcs_ese}
                                onChange={(e) =>
                                  setEcapPositions((rows) =>
                                    rows.map((r, i) =>
                                      i === index ? { ...r, job_code_pcs_ese: e.target.value } : r,
                                    ),
                                  )
                                }
                              />
                            </div>
                            <div className="flex gap-2 items-end">
                              <div className="space-y-1 flex-1">
                                <Label className="text-xs">EMA</Label>
                                <Input
                                  type="number"
                                  min={0}
                                  step="0.01"
                                  value={row.annual_average_count}
                                  onChange={(e) =>
                                    setEcapPositions((rows) =>
                                      rows.map((r, i) =>
                                        i === index
                                          ? { ...r, annual_average_count: parseFloat(e.target.value) || 0 }
                                          : r,
                                      ),
                                    )
                                  }
                                />
                              </div>
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                onClick={() =>
                                  setEcapPositions((rows) => rows.filter((_, i) => i !== index))
                                }
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => ecapMutation.mutate()}
                      disabled={ecapMutation.isPending}
                    >
                      Enregistrer les postes ECAP
                    </Button>
                  </div>

                  <div className="rounded-lg border p-4 space-y-3">
                    <p className="text-sm font-medium">Réconciliation URSSAF (notification mars)</p>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="space-y-1">
                        <Label className="text-xs">EMA assujettissement URSSAF</Label>
                        <Input
                          value={urssafEma.assujettissement}
                          onChange={(e) =>
                            setUrssafEma((u) => ({ ...u, assujettissement: e.target.value }))
                          }
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">EMA BOETH URSSAF</Label>
                        <Input
                          value={urssafEma.boeth}
                          onChange={(e) => setUrssafEma((u) => ({ ...u, boeth: e.target.value }))}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">EMA ECAP URSSAF</Label>
                        <Input
                          value={urssafEma.ecap}
                          onChange={(e) => setUrssafEma((u) => ({ ...u, ecap: e.target.value }))}
                        />
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => urssafMutation.mutate()}
                      disabled={urssafMutation.isPending}
                    >
                      Appliquer les EMA URSSAF
                    </Button>
                  </div>
                  <Button onClick={() => computeMutation.mutate()} disabled={computeMutation.isPending}>
                    Recalculer la DOETH {reviewYear}
                  </Button>
                </>
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
