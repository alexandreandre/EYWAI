/**
 * Simulation arrêt maladie — même moteur maintien que le bulletin.
 */

import { useMemo, useState } from 'react';
import { format } from 'date-fns';
import { useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';

import {
  simulerArretMaladie,
  SIMULATION_ARRET_MALADIE_TYPES,
  type SimulationArretMaladieArretType,
  type SimulationArretMaladieResult,
} from '@/api/simulation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { MaintenanceDetailModal } from '@/components/payslip/MaintenanceDetailModal';

interface Employee {
  id: string;
  first_name: string;
  last_name: string;
  statut?: string;
}

const ARRET_TYPE_LABELS: Record<SimulationArretMaladieArretType, string> = {
  maladie_simple: 'Maladie simple',
  accident_travail: 'Accident du travail',
  maladie_professionnelle: 'Maladie professionnelle',
  accident_trajet: 'Accident de trajet',
  mi_temps_therapeutique: 'Mi-temps thérapeutique',
  ald: 'ALD',
  rechute_at: 'Rechute AT',
  arret_exceptionnel: 'Arrêt exceptionnel',
};

function alertBannerClass(text: string): string {
  const t = text.toLowerCase();
  if (t.includes('non calculables')) {
    return 'rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive';
  }
  if (t.includes('ijss versées directement')) {
    return 'rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-950 dark:bg-blue-950/30 dark:text-blue-100';
  }
  if (
    t.includes('insuffisante') ||
    t.includes('plafonné') ||
    t.includes('prévoyance relais') ||
    t.includes('conventionnelle moins favorable')
  ) {
    return 'rounded-md border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-950 dark:bg-orange-950/20 dark:text-orange-100';
  }
  return 'rounded-md border border-muted bg-muted/40 px-3 py-2 text-sm';
}

const eur = (n: number) =>
  new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 2,
  }).format(n);

interface ArretMaladieSimulationTabProps {
  employees: Employee[];
}

export function ArretMaladieSimulationTab({ employees }: ArretMaladieSimulationTabProps) {
  const todayIso = useMemo(() => format(new Date(), 'yyyy-MM-dd'), []);

  const [employeeId, setEmployeeId] = useState('');
  const [dureeJours, setDureeJours] = useState(7);
  const [arretType, setArretType] = useState<SimulationArretMaladieArretType>('maladie_simple');
  const [dateDebut, setDateDebut] = useState(todayIso);
  const [subrogationActive, setSubrogationActive] = useState(true);
  const [nombreEnfants, setNombreEnfants] = useState(0);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [statutOverride, setStatutOverride] = useState<'auto' | 'Cadre' | 'Non-Cadre'>('auto');
  const [salaireOverride, setSalaireOverride] = useState('');
  const [ancienneteOverride, setAncienneteOverride] = useState('');
  const [result, setResult] = useState<SimulationArretMaladieResult | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const mutation = useMutation({
    mutationFn: simulerArretMaladie,
    onSuccess: (data) => {
      setResult(data);
      setFormError(null);
    },
    onError: (err: unknown) => {
      const ax = err as { response?: { data?: { detail?: unknown } } };
      const d = ax.response?.data?.detail;
      setFormError(typeof d === 'string' ? d : 'Simulation impossible.');
    },
  });

  const handleSimuler = () => {
    setFormError(null);
    if (!employeeId) {
      setFormError('Veuillez sélectionner un employé.');
      return;
    }
    if (dureeJours < 1 || dureeJours > 365) {
      setFormError('La durée doit être entre 1 et 365 jours.');
      return;
    }
    const salaireNum = salaireOverride.trim() === '' ? null : Number(salaireOverride);
    const ancienneteNum =
      ancienneteOverride.trim() === '' ? null : Number(ancienneteOverride);
    mutation.mutate({
      employee_id: employeeId,
      duree_jours: dureeJours,
      arret_type: arretType,
      subrogation_active: subrogationActive,
      date_debut: dateDebut,
      nombre_enfants: nombreEnfants,
      salaire_base_override:
        salaireNum != null && Number.isFinite(salaireNum) && salaireNum > 0
          ? salaireNum
          : null,
      statut_override: statutOverride === 'auto' ? null : statutOverride,
      anciennete_mois_override:
        ancienneteNum != null && Number.isFinite(ancienneteNum) && ancienneteNum >= 0
          ? Math.round(ancienneteNum)
          : null,
    });
  };

  const handleReset = () => {
    setResult(null);
    setFormError(null);
    mutation.reset();
  };

  const syn = result?.synthese;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2 sm:col-span-2">
          <Label>Employé</Label>
          <Select value={employeeId || undefined} onValueChange={setEmployeeId}>
            <SelectTrigger>
              <SelectValue placeholder="Sélectionner un employé…" />
            </SelectTrigger>
            <SelectContent>
              {employees.map((e) => (
                <SelectItem key={e.id} value={e.id}>
                  {e.first_name} {e.last_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="duree-arret">Durée (jours)</Label>
          <Input
            id="duree-arret"
            type="number"
            min={1}
            max={365}
            value={dureeJours}
            onChange={(ev) => setDureeJours(Math.min(365, Math.max(1, Number(ev.target.value) || 1)))}
          />
        </div>

        <div className="space-y-2">
          <Label>Type d&apos;arrêt</Label>
          <Select
            value={arretType}
            onValueChange={(v) => setArretType(v as SimulationArretMaladieArretType)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SIMULATION_ARRET_MALADIE_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {ARRET_TYPE_LABELS[t]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="date-debut-arret">Date de début de l&apos;arrêt</Label>
          <Input
            id="date-debut-arret"
            type="date"
            value={dateDebut}
            onChange={(ev) => setDateDebut(ev.target.value)}
          />
        </div>

        <div className="flex items-center justify-between rounded-md border p-3">
          <div className="space-y-0.5">
            <Label htmlFor="subrogation-sim">Subrogation</Label>
            <p className="text-xs text-muted-foreground">IJSS versées par l&apos;employeur</p>
          </div>
          <Switch
            id="subrogation-sim"
            checked={subrogationActive}
            onCheckedChange={setSubrogationActive}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="nb-enfants">Enfants à charge</Label>
          <Input
            id="nb-enfants"
            type="number"
            min={0}
            max={10}
            value={nombreEnfants}
            onChange={(ev) =>
              setNombreEnfants(Math.min(10, Math.max(0, Number(ev.target.value) || 0)))
            }
          />
        </div>
      </div>

      <div className="rounded-md border">
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium"
        >
          <span>Paramètres what-if (statut, ancienneté, salaire)</span>
          <span className="text-xs text-muted-foreground">
            {showAdvanced ? 'Masquer' : 'Afficher'}
          </span>
        </button>
        {showAdvanced ? (
          <div className="grid gap-4 border-t p-3 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>Statut</Label>
              <Select
                value={statutOverride}
                onValueChange={(v) =>
                  setStatutOverride(v as 'auto' | 'Cadre' | 'Non-Cadre')
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Fiche salarié</SelectItem>
                  <SelectItem value="Cadre">Cadre</SelectItem>
                  <SelectItem value="Non-Cadre">Non-Cadre</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="anciennete-override">Ancienneté (mois)</Label>
              <Input
                id="anciennete-override"
                type="number"
                min={0}
                max={600}
                placeholder="Fiche salarié"
                value={ancienneteOverride}
                onChange={(ev) => setAncienneteOverride(ev.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="salaire-override">Salaire brut mensuel (€)</Label>
              <Input
                id="salaire-override"
                type="number"
                min={0}
                placeholder="Fiche salarié"
                value={salaireOverride}
                onChange={(ev) => setSalaireOverride(ev.target.value)}
              />
            </div>
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" onClick={handleSimuler} disabled={mutation.isPending}>
          {mutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Calcul…
            </>
          ) : (
            'Simuler'
          )}
        </Button>
        {result ? (
          <Button type="button" variant="outline" onClick={handleReset}>
            Nouvelle simulation
          </Button>
        ) : null}
      </div>

      {formError ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {formError}
        </div>
      ) : null}

      {mutation.isPending ? (
        <div className="space-y-2 py-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full max-w-md" />
          <Skeleton className="h-10 w-2/3 max-w-sm" />
        </div>
      ) : null}

      {result && syn ? (
        <div className="space-y-6 border-t pt-6">
          {result.profil ? (
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-muted px-2.5 py-1">
                Statut : <span className="font-medium">{result.profil.statut || '—'}</span>
                {result.profil.est_cadre ? ' (cadre)' : ''}
              </span>
              <span className="rounded-full bg-muted px-2.5 py-1">
                Ancienneté : <span className="font-medium">{result.profil.anciennete_annees} an(s)</span>
              </span>
              <span className="rounded-full bg-muted px-2.5 py-1">
                Maintien légal :{' '}
                <span className="font-medium">
                  {result.profil.duree_maintien_legale_jours} j
                </span>{' '}
                ({result.profil.duree_par_taux_jours} j à 90 % + {result.profil.duree_par_taux_jours} j à 66,66 %)
              </span>
              <span className="rounded-full bg-muted px-2.5 py-1">
                Carence employeur : <span className="font-medium">{result.profil.carence_employeur_jours} j</span>
              </span>
            </div>
          ) : null}

          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Impact net salarié
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p
                  className={`text-2xl font-semibold tabular-nums ${
                    syn.impact_net_salarie < 0 ? 'text-red-600' : 'text-foreground'
                  }`}
                >
                  {eur(syn.impact_net_salarie)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Maintien versé
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold tabular-nums">{eur(syn.maintien_verse)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Coût employeur total
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold tabular-nums">{eur(syn.cout_employeur_total)}</p>
              </CardContent>
            </Card>
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold">Détail des montants</h3>
            <div className="overflow-hidden rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Libellé</TableHead>
                    <TableHead className="text-right">Montant</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell>Salaire mensuel de base</TableCell>
                    <TableCell className="text-right tabular-nums">{eur(syn.salaire_mensuel_base)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>IJSS théoriques</TableCell>
                    <TableCell className="text-right tabular-nums">{eur(syn.ijss_theorique)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Maintien versé</TableCell>
                    <TableCell className="text-right tabular-nums">{eur(syn.maintien_verse)}</TableCell>
                  </TableRow>
                  {syn.prevoyance_montant > 0 ? (
                    <TableRow>
                      <TableCell>
                        Complément prévoyance
                        <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                          (versé par l&apos;organisme assureur, hors coût employeur direct)
                        </span>
                      </TableCell>
                      <TableCell className="text-right tabular-nums align-top">
                        {eur(syn.prevoyance_montant)}
                      </TableCell>
                    </TableRow>
                  ) : null}
                  <TableRow>
                    <TableCell>Complément employeur</TableCell>
                    <TableCell className="text-right tabular-nums">{eur(syn.cout_employeur_complement)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>
                      Charges patronales estimées
                      <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                        (estimation forfaitaire 42 % du complément)
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums align-top">
                      {eur(syn.charges_patronales_estimees)}
                    </TableCell>
                  </TableRow>
                  <TableRow className="bg-muted/40 font-medium">
                    <TableCell>Coût total employeur</TableCell>
                    <TableCell className="text-right tabular-nums">{eur(syn.cout_employeur_total)}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </div>

          {result.alertes?.length ? (
            <div className="space-y-2">
              <h3 className="text-sm font-semibold">Alertes</h3>
              <ul className="space-y-2">
                {result.alertes.map((a, i) => (
                  <li key={i} className={alertBannerClass(a)}>
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <Button type="button" variant="outline" onClick={() => setDetailOpen(true)}>
            Voir détail du calcul
          </Button>
        </div>
      ) : null}

      {result ? (
        <MaintenanceDetailModal
          open={detailOpen}
          onClose={() => setDetailOpen(false)}
          maintien={result.resultats_maintien}
        />
      ) : null}
    </div>
  );
}
