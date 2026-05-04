import { useMemo, useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Calculator, Loader2, TrendingUp } from 'lucide-react';

import {
  appliquerAugmentationCollective,
  genererAvenantsLot,
  simulerAugmentationCollective,
  type EmployeSimule,
  type SimulationCollectiveResultat,
} from '@/api/augmentations';
import {
  downloadDocument,
  getDocuments,
  triggerSignedDocumentDownload,
  updateDocumentStatus,
  type DocumentStatus,
  type GeneratedDocument,
} from '@/api/documents';
import { listCompanyServices } from '@/api/objectives';
import { useCompany } from '@/contexts/CompanyContext';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ToastAction } from '@/components/ui/toast';
import { toast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';

const AVENANTS_QK = ['documents', 'avenant_salaire'] as const;

function formatEuroAmount(n: number): string {
  return `${n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function formatDateFR(iso: string): string {
  if (!iso) return '';
  const d = iso.includes('T') ? new Date(iso) : new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('fr-FR');
}

function formatDateTimeGen(iso: string): string {
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

/** Déduit les IDs réellement mis à jour à partir des lignes d’erreur retournées par l’API. */
function computeAppliedEmployeeIds(requestedIds: string[], erreurs: string[]): string[] {
  const failed = new Set<string>();
  for (const line of erreurs) {
    for (const id of requestedIds) {
      if (line.startsWith(`${id}:`)) {
        failed.add(id);
        break;
      }
    }
  }
  return requestedIds.filter((id) => !failed.has(id));
}

function docDateEffetDisplay(d: GeneratedDocument): string {
  const ctx = d.generation_context;
  if (!ctx || typeof ctx !== 'object') return '—';
  const raw = (ctx as Record<string, unknown>).date_effet;
  if (typeof raw !== 'string' || !raw.trim()) return '—';
  return formatDateFR(raw);
}

function statusBadge(status: string) {
  const map: Record<string, { className: string; label: string }> = {
    brouillon: { className: 'bg-amber-100 text-amber-900 border-amber-200', label: 'Brouillon' },
    envoye: { className: 'bg-blue-100 text-blue-900 border-blue-200', label: 'Envoyé' },
    signe: { className: 'bg-emerald-100 text-emerald-900 border-emerald-200', label: 'Signé' },
    archive: { className: 'bg-slate-100 text-slate-700 border-slate-200', label: 'Archivé' },
  };
  const m = map[status] ?? { className: 'bg-muted text-muted-foreground', label: status };
  return (
    <Badge variant="outline" className={cn('font-medium', m.className)}>
      {m.label}
    </Badge>
  );
}

export default function AugmentationsCollectives() {
  const navigate = useNavigate();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const queryClient = useQueryClient();

  const servicesQuery = useQuery({
    queryKey: ['objectives-services'],
    queryFn: () => listCompanyServices(),
    enabled: Boolean(companyId),
  });

  const avenantsQuery = useQuery({
    queryKey: [...AVENANTS_QK, companyId],
    queryFn: () => getDocuments({ document_type: 'avenant_salaire' }),
    enabled: Boolean(companyId),
  });

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: DocumentStatus }) =>
      updateDocumentStatus(id, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...AVENANTS_QK, companyId] });
      toast({ title: 'Statut mis à jour' });
    },
    onError: () => {
      toast({
        title: 'Mise à jour impossible',
        description: 'Réessayez plus tard.',
        variant: 'destructive',
      });
    },
  });

  const [filterServiceId, setFilterServiceId] = useState<string>('');
  const [filterStatut, setFilterStatut] = useState<string>('');
  const [filterContract, setFilterContract] = useState<string>('');
  const [ancienneteMinMois, setAncienneteMinMois] = useState('');
  const [salaireMin, setSalaireMin] = useState('');
  const [salaireMax, setSalaireMax] = useState('');

  const [simType, setSimType] = useState<'pourcentage' | 'montant_fixe'>('pourcentage');
  const [valeurSim, setValeurSim] = useState('');
  const [effectiveDate, setEffectiveDate] = useState(() => new Date().toISOString().slice(0, 10));

  const [simLoading, setSimLoading] = useState(false);
  const [simResult, setSimResult] = useState<SimulationCollectiveResultat | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const [applyOpen, setApplyOpen] = useState(false);
  const [applyMotif, setApplyMotif] = useState('');
  const [applySubmitting, setApplySubmitting] = useState(false);
  const [applySuccessContext, setApplySuccessContext] = useState<{
    nb_appliques: number;
    appliedIds: string[];
  } | null>(null);
  const applySuccessRef = useRef(applySuccessContext);
  applySuccessRef.current = applySuccessContext;

  const [lotGenOpen, setLotGenOpen] = useState(false);
  const [lotEmployeeIds, setLotEmployeeIds] = useState<string[]>([]);
  const [lotEffectiveDateInput, setLotEffectiveDateInput] = useState('');
  const [lotMotifInput, setLotMotifInput] = useState('');
  const [lotSubmitting, setLotSubmitting] = useState(false);

  const employesSimules = simResult?.employes ?? [];

  useEffect(() => {
    if (!simResult?.employes?.length) {
      setSelectedIds(new Set());
      return;
    }
    setSelectedIds(new Set(simResult.employes.map((e) => e.employee_id)));
  }, [simResult]);

  const allSelected = useMemo(() => {
    if (!employesSimules.length) return false;
    return employesSimules.every((e) => selectedIds.has(e.employee_id));
  }, [employesSimules, selectedIds]);

  const toggleOne = (id: string, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const toggleAll = (checked: boolean) => {
    if (!checked || !employesSimules.length) {
      setSelectedIds(new Set());
      return;
    }
    setSelectedIds(new Set(employesSimules.map((e) => e.employee_id)));
  };

  const parseOptionalFloat = (s: string): number | null => {
    const t = s.trim();
    if (!t) return null;
    const n = parseFloat(t.replace(',', '.'));
    return Number.isNaN(n) ? null : n;
  };

  const parseOptionalInt = (s: string): number | null => {
    const t = s.trim();
    if (!t) return null;
    const n = parseInt(t, 10);
    return Number.isNaN(n) ? null : n;
  };

  const resetSimulationUi = () => {
    setSimResult(null);
    setValeurSim('');
    setApplyMotif('');
    setApplySuccessContext(null);
  };

  const handleSimulate = async () => {
    if (!companyId) {
      toast({ title: 'Entreprise active requise', variant: 'destructive' });
      return;
    }
    const v = parseFloat(valeurSim.replace(',', '.'));
    if (Number.isNaN(v) || v <= 0) {
      toast({ title: 'Indiquez une valeur positive.', variant: 'destructive' });
      return;
    }
    const smin = parseOptionalFloat(salaireMin);
    const smax = parseOptionalFloat(salaireMax);
    const am = parseOptionalInt(ancienneteMinMois);

    setSimLoading(true);
    try {
      const data = await simulerAugmentationCollective(companyId, {
        filtres: {
          service_id: filterServiceId || null,
          statut: filterStatut || null,
          contract_type: filterContract || null,
          anciennete_min_mois: am,
          salaire_min: smin,
          salaire_max: smax,
        },
        type_augmentation: simType,
        valeur: v,
        effective_date: effectiveDate,
      });
      setSimResult(data);
      toast({
        title: 'Simulation prête',
        description: `${data.nb_employes} salarié(s) correspondant aux filtres.`,
      });
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: 'Simulation impossible',
        description: typeof msg === 'string' ? msg : 'Réessayez plus tard.',
        variant: 'destructive',
      });
    } finally {
      setSimLoading(false);
    }
  };

  const handleApply = async () => {
    if (!companyId || !simResult) return;
    const requested = [...selectedIds];
    if (!requested.length) return;
    const v = parseFloat(valeurSim.replace(',', '.'));
    if (Number.isNaN(v) || v <= 0) return;

    setApplySubmitting(true);
    try {
      const res = await appliquerAugmentationCollective(companyId, {
        employee_ids: requested,
        type_augmentation: simType,
        valeur: v,
        effective_date: effectiveDate,
        motif: applyMotif.trim() || undefined,
      });

      toast({
        title: 'Augmentations appliquées',
        description: `${res.nb_appliques} augmentation(s) enregistrée(s).`,
      });
      if (res.nb_erreurs > 0) {
        toast({
          title: 'Certaines lignes ont échoué',
          description: res.erreurs.slice(0, 5).join(' · ') + (res.erreurs.length > 5 ? '…' : ''),
          variant: 'destructive',
        });
      }

      const appliedIds = computeAppliedEmployeeIds(requested, res.erreurs);

      if (res.nb_appliques <= 0) {
        setApplyOpen(false);
        resetSimulationUi();
      } else {
        setApplySuccessContext({
          nb_appliques: res.nb_appliques,
          appliedIds,
        });
      }
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: 'Application impossible',
        description: typeof msg === 'string' ? msg : 'Réessayez plus tard.',
        variant: 'destructive',
      });
    } finally {
      setApplySubmitting(false);
    }
  };

  const closeApplyFlow = () => {
    setApplyOpen(false);
    resetSimulationUi();
  };

  const openLotDialogFromApplySuccess = () => {
    if (!applySuccessContext?.appliedIds.length) return;
    setLotEmployeeIds(applySuccessContext.appliedIds);
    setLotEffectiveDateInput(effectiveDate);
    setLotMotifInput(applyMotif.trim());
    setApplyOpen(false);
    setApplySuccessContext(null);
    setLotGenOpen(true);
  };

  const handleLotGenerate = async () => {
    if (!companyId || !lotEmployeeIds.length) return;
    setLotSubmitting(true);
    try {
      const nouveauParEmploye: Record<string, number> = {};
      if (simResult?.employes?.length && lotEmployeeIds.length) {
        const wanted = new Set(lotEmployeeIds);
        for (const e of simResult.employes) {
          if (wanted.has(e.employee_id)) {
            nouveauParEmploye[e.employee_id] = e.nouveau_salaire_brut;
          }
        }
      }

      const res = await genererAvenantsLot(companyId, {
        employee_ids: lotEmployeeIds,
        effective_date: lotEffectiveDateInput,
        motif: lotMotifInput.trim() || undefined,
        ...(Object.keys(nouveauParEmploye).length > 0
          ? { nouveau_salaire_par_employe: nouveauParEmploye }
          : {}),
      });

      toast({
        title: `${res.nb_generes} avenant(s) généré(s).`,
        description: 'Disponibles dans Documents RH pour signature.',
        action: (
          <ToastAction altText="Ouvrir Documents RH" onClick={() => navigate('/documents')}>
            Ouvrir Documents RH
          </ToastAction>
        ),
      });

      if (res.nb_erreurs > 0) {
        toast({
          title: `${res.nb_erreurs} génération(s) en erreur`,
          description: res.erreurs.slice(0, 5).join(' · ') + (res.erreurs.length > 5 ? '…' : ''),
        });
      }

      await queryClient.invalidateQueries({ queryKey: [...AVENANTS_QK, companyId] });
      setLotGenOpen(false);
      setLotEmployeeIds([]);
      resetSimulationUi();
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: 'Génération impossible',
        description: typeof msg === 'string' ? msg : 'Réessayez plus tard.',
        variant: 'destructive',
      });
    } finally {
      setLotSubmitting(false);
    }
  };

  const handleDownloadDoc = async (d: GeneratedDocument) => {
    try {
      const r = await downloadDocument(d.id);
      triggerSignedDocumentDownload(r, d.file_name || 'avenant.pdf');
    } catch {
      toast({
        title: 'Téléchargement',
        description: 'Impossible d’obtenir le lien.',
        variant: 'destructive',
      });
    }
  };

  const ligneAugmentation = (e: EmployeSimule) => {
    const pct =
      e.ancien_salaire_brut > 0
        ? ((e.nouveau_salaire_brut - e.ancien_salaire_brut) / e.ancien_salaire_brut) * 100
        : 0;
    return (
      <span className="font-medium text-emerald-700 whitespace-nowrap">
        +{formatEuroAmount(e.difference_brut)} (+
        {pct.toLocaleString('fr-FR', { maximumFractionDigits: 2 })}
        %)
      </span>
    );
  };

  const rowsAvenants = avenantsQuery.data ?? [];

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <TrendingUp className="h-7 w-7 text-muted-foreground" />
          Augmentations collectives
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Filtrez les salariés, simulez l&apos;impact puis appliquez aux profils sélectionnés.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(260px,320px)_1fr]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="text-base">Sélection des salariés</CardTitle>
            <CardDescription>Filtres appliqués aux collaborateurs actifs.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Service</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={filterServiceId}
                onChange={(e) => setFilterServiceId(e.target.value)}
                disabled={servicesQuery.isLoading}
              >
                <option value="">Tous</option>
                {(servicesQuery.data ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label>Statut</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={filterStatut}
                onChange={(e) => setFilterStatut(e.target.value)}
              >
                <option value="">Tous</option>
                <option value="Cadre">Cadre</option>
                <option value="Non-Cadre">Non-Cadre</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>Type de contrat</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={filterContract}
                onChange={(e) => setFilterContract(e.target.value)}
              >
                <option value="">Tous</option>
                <option value="CDI">CDI</option>
                <option value="CDD">CDD</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="filtre-anciennete">Ancienneté minimum (mois)</Label>
              <Input
                id="filtre-anciennete"
                type="number"
                min={0}
                placeholder="Ex. 12"
                value={ancienneteMinMois}
                onChange={(e) => setAncienneteMinMois(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="smin">Salaire min (€)</Label>
                <Input
                  id="smin"
                  type="number"
                  min={0}
                  step="100"
                  value={salaireMin}
                  onChange={(e) => setSalaireMin(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="smax">Salaire max (€)</Label>
                <Input
                  id="smax"
                  type="number"
                  min={0}
                  step="100"
                  value={salaireMax}
                  onChange={(e) => setSalaireMax(e.target.value)}
                />
              </div>
            </div>

            <div className="border-t pt-4 space-y-3">
              <Label>Type d&apos;augmentation</Label>
              <RadioGroup
                value={simType}
                onValueChange={(val) => setSimType(val as 'pourcentage' | 'montant_fixe')}
                className="flex flex-col gap-2"
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="pourcentage" id="col-pct" />
                  <Label htmlFor="col-pct" className="font-normal cursor-pointer">
                    Pourcentage
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="montant_fixe" id="col-fixe" />
                  <Label htmlFor="col-fixe" className="font-normal cursor-pointer">
                    Montant fixe
                  </Label>
                </div>
              </RadioGroup>
              <div className="space-y-2">
                <Label htmlFor="col-val">{simType === 'pourcentage' ? 'Valeur (%)' : 'Montant (€)'}</Label>
                <Input
                  id="col-val"
                  type="number"
                  min={0}
                  step={simType === 'pourcentage' ? '0.1' : '1'}
                  value={valeurSim}
                  onChange={(e) => setValeurSim(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="col-date">Date d&apos;effet</Label>
                <Input
                  id="col-date"
                  type="date"
                  value={effectiveDate}
                  onChange={(e) => setEffectiveDate(e.target.value)}
                />
              </div>
              <Button
                type="button"
                className="w-full"
                disabled={simLoading || !companyId || !valeurSim.trim()}
                onClick={() => void handleSimulate()}
              >
                {simLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Calculator className="mr-2 h-4 w-4" />
                )}
                Simuler l&apos;impact
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          {simResult && (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Salariés concernés</CardDescription>
                    <CardTitle className="text-2xl tabular-nums">{simResult.nb_employes}</CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Impact masse salariale</CardDescription>
                    <CardTitle className="text-xl tabular-nums text-emerald-700">
                      +{formatEuroAmount(simResult.difference_masse_salariale)}/mois
                    </CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Charges patronales supplémentaires</CardDescription>
                    <CardTitle className="text-xl tabular-nums text-emerald-700">
                      +{formatEuroAmount(simResult.cout_charges_patronales_supplementaires)}/mois
                    </CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Coût total employeur supplémentaire</CardDescription>
                    <CardTitle className="text-xl tabular-nums text-emerald-700">
                      +{formatEuroAmount(simResult.cout_total_supplementaire)}/mois
                    </CardTitle>
                  </CardHeader>
                </Card>
              </div>

              <Card>
                <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4">
                  <div>
                    <CardTitle>Détail par salarié</CardTitle>
                    <CardDescription>Sélectionnez ceux à inclure dans l&apos;application.</CardDescription>
                  </div>
                  <Button
                    type="button"
                    disabled={!selectedIds.size}
                    onClick={() => setApplyOpen(true)}
                  >
                    Appliquer aux salariés sélectionnés
                  </Button>
                </CardHeader>
                <CardContent className="w-full overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Nom</TableHead>
                        <TableHead>Poste</TableHead>
                        <TableHead>Ancien brut</TableHead>
                        <TableHead>Nouveau brut</TableHead>
                        <TableHead>Augmentation</TableHead>
                        <TableHead className="w-[120px] text-center">
                          <div className="flex flex-col items-center gap-1">
                            <span>Sélectionné</span>
                            <Checkbox
                              checked={allSelected}
                              onCheckedChange={(c) => toggleAll(c === true)}
                              aria-label="Tout sélectionner"
                            />
                          </div>
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {employesSimules.map((e) => (
                        <TableRow key={e.employee_id}>
                          <TableCell className="font-medium">{e.nom_complet}</TableCell>
                          <TableCell>{e.poste ?? '—'}</TableCell>
                          <TableCell>{formatEuroAmount(e.ancien_salaire_brut)}</TableCell>
                          <TableCell>{formatEuroAmount(e.nouveau_salaire_brut)}</TableCell>
                          <TableCell>{ligneAugmentation(e)}</TableCell>
                          <TableCell className="text-center">
                            <Checkbox
                              checked={selectedIds.has(e.employee_id)}
                              onCheckedChange={(c) => toggleOne(e.employee_id, c === true)}
                              aria-label={`Sélectionner ${e.nom_complet}`}
                            />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          )}

          {!simResult && (
            <Card className="border-dashed">
              <CardContent className="py-12 text-center text-sm text-muted-foreground">
                Renseignez les filtres et lancez une simulation pour voir l&apos;impact sur la masse salariale.
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <Separator />

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Suivi des avenants émis</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Avenants salaire générés pour l&apos;entreprise active — même liste que Documents RH, filtrée ici.
          </p>
        </div>

        <Card>
          <CardContent className="pt-6">
            {avenantsQuery.isLoading && (
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex gap-4">
                    <Skeleton className="h-10 flex-1" />
                    <Skeleton className="h-10 w-32" />
                    <Skeleton className="h-10 w-32" />
                  </div>
                ))}
              </div>
            )}
            {avenantsQuery.isError && (
              <p className="text-sm text-destructive text-center py-8">
                Impossible de charger les avenants.
              </p>
            )}
            {!avenantsQuery.isLoading && !avenantsQuery.isError && rowsAvenants.length === 0 && (
              <p className="py-12 text-center text-sm text-muted-foreground">
                Aucun avenant salaire généré.
              </p>
            )}
            {!avenantsQuery.isLoading && !avenantsQuery.isError && rowsAvenants.length > 0 && (
              <div className="w-full overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Salarié</TableHead>
                      <TableHead>Date génération</TableHead>
                      <TableHead>Date d&apos;effet</TableHead>
                      <TableHead>Statut</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rowsAvenants.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell className="font-medium">{d.employee_name ?? '—'}</TableCell>
                        <TableCell className="whitespace-nowrap text-sm">
                          {formatDateTimeGen(d.created_at)}
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-sm">{docDateEffetDisplay(d)}</TableCell>
                        <TableCell>{statusBadge(d.status)}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex flex-wrap items-center justify-end gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={!d.file_url}
                              onClick={() => void handleDownloadDoc(d)}
                            >
                              Télécharger
                            </Button>
                            <Select
                              value={d.status}
                              onValueChange={(v) =>
                                statusMut.mutate({ id: d.id, status: v as DocumentStatus })
                              }
                              disabled={statusMut.isPending}
                            >
                              <SelectTrigger className="h-8 w-[130px]">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="brouillon">Brouillon</SelectItem>
                                <SelectItem value="envoye">Envoyé</SelectItem>
                                <SelectItem value="signe">Signé</SelectItem>
                                <SelectItem value="archive">Archivé</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <Dialog
        open={applyOpen}
        onOpenChange={(open) => {
          if (!open) {
            const hadSuccessStep = applySuccessRef.current !== null;
            setApplyOpen(false);
            if (hadSuccessStep) {
              resetSimulationUi();
            }
          } else {
            setApplyOpen(true);
          }
        }}
      >
        <DialogContent>
          {!applySuccessContext ? (
            <>
              <DialogHeader>
                <DialogTitle>Confirmer l&apos;application</DialogTitle>
                <DialogDescription>
                  Appliquer une augmentation à {selectedIds.size} salarié(s) sélectionné(s) ?
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-2 py-2">
                <Label htmlFor="motif-col">Motif (optionnel, commun)</Label>
                <Input
                  id="motif-col"
                  value={applyMotif}
                  onChange={(e) => setApplyMotif(e.target.value)}
                  placeholder="Ex. revue salariale annuelle"
                />
                <p className="text-xs text-muted-foreground">
                  Date d&apos;effet : {formatDateFR(effectiveDate)}
                </p>
              </div>
              <DialogFooter className="gap-2 sm:gap-0">
                <Button variant="outline" onClick={() => setApplyOpen(false)}>
                  Annuler
                </Button>
                <Button onClick={() => void handleApply()} disabled={applySubmitting || !selectedIds.size}>
                  {applySubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Confirmer
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>Augmentations enregistrées</DialogTitle>
                <DialogDescription>
                  {applySuccessContext.nb_appliques} augmentation(s) ont été appliquée(s) avec succès.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-end">
                <Button variant="outline" onClick={() => closeApplyFlow()}>
                  Fermer
                </Button>
                {applySuccessContext.nb_appliques > 0 ? (
                  <Button type="button" onClick={() => openLotDialogFromApplySuccess()}>
                    Générer les avenants salaire
                  </Button>
                ) : null}
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={lotGenOpen} onOpenChange={setLotGenOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Générer les avenants en lot</DialogTitle>
            <DialogDescription>
              Générer un avenant salaire pour {lotEmployeeIds.length} salarié(s).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="lot-date">Date d&apos;effet</Label>
              <Input
                id="lot-date"
                type="date"
                value={lotEffectiveDateInput}
                onChange={(e) => setLotEffectiveDateInput(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="lot-motif">Motif (optionnel)</Label>
              <Input
                id="lot-motif"
                value={lotMotifInput}
                onChange={(e) => setLotMotifInput(e.target.value)}
                placeholder="Commun à tous les avenants"
              />
            </div>
            <p className="text-xs text-muted-foreground rounded-md border border-muted bg-muted/30 px-3 py-2">
              Les avenants seront disponibles dans Documents RH pour signature.
            </p>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setLotGenOpen(false)}>
              Annuler
            </Button>
            <Button
              type="button"
              onClick={() => void handleLotGenerate()}
              disabled={
                lotSubmitting ||
                !lotEmployeeIds.length ||
                !lotEffectiveDateInput.trim()
              }
            >
              {lotSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Générer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
