import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { differenceInCalendarDays, format, parseISO } from 'date-fns';
import { fr } from 'date-fns/locale';
import { Loader2 } from 'lucide-react';
import {
  applyBareme,
  confirmTrialPeriod,
  fetchTrialPeriodTracking,
  type EmployeeToQualify,
  type TrialPeriod,
} from '@/api/trialPeriods';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { toast } from '@/components/ui/use-toast';

const TRACKING_KEY = ['trial-periods', 'tracking'] as const;

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return format(parseISO(iso.slice(0, 10)), 'd MMMM yyyy', { locale: fr });
}

function daysLeft(iso: string): number {
  return differenceInCalendarDays(parseISO(iso.slice(0, 10)), new Date());
}

function errorMessage(error: unknown, fallback: string): string {
  return (
    (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback
  );
}

export default function TrialPeriods() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const { data, isLoading, isError } = useQuery({
    queryKey: TRACKING_KEY,
    queryFn: fetchTrialPeriodTracking,
  });

  // Déclaré avant les mutations : leurs callbacks s'en servent pour nommer les
  // salariés écartés.
  const nameOf = (employeeId: string): string => {
    const emp = data?.a_qualifier.find((e) => e.id === employeeId);
    return emp ? `${emp.first_name} ${emp.last_name}`.trim() : employeeId;
  };

  const confirmMutation = useMutation({
    mutationFn: confirmTrialPeriod,
    onSuccess: () => {
      toast({ title: 'Embauche confirmée', description: "Le suivi de période d'essai est clos." });
      void queryClient.invalidateQueries({ queryKey: TRACKING_KEY });
    },
    onError: (error) =>
      toast({
        title: 'Erreur',
        description: errorMessage(error, "Impossible de confirmer l'embauche."),
        variant: 'destructive',
      }),
  });

  const applyMutation = useMutation({
    mutationFn: applyBareme,
    onSuccess: (result) => {
      // Une sélection partiellement traitée ne doit pas passer pour un succès
      // complet : les salariés écartés sont nommés avec leur raison.
      if (result.skipped.length > 0) {
        toast({
          title: `${result.created.length} période(s) créée(s), ${result.skipped.length} écartée(s)`,
          description: result.skipped.map((s) => `${nameOf(s.employee_id)} : ${s.raison}`).join(' · '),
        });
      } else {
        toast({ title: `${result.created.length} période(s) d'essai créée(s)` });
      }
      setSelected(new Set());
      void queryClient.invalidateQueries({ queryKey: TRACKING_KEY });
    },
    onError: (error) =>
      toast({
        title: 'Erreur',
        description: errorMessage(error, "Impossible d'appliquer le barème."),
        variant: 'destructive',
      }),
  });

  const toggle = (employeeId: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-8 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Chargement des périodes d&apos;essai…
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-8 text-destructive">Impossible de charger les périodes d&apos;essai.</div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Périodes d&apos;essai</h1>
        <p className="text-sm text-muted-foreground">
          Suivi des périodes en cours, des confirmations à prononcer et des embauches récentes
          encore sans période d&apos;essai. Alerte réglée à {data.alert_days} jours.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>À confirmer ({data.a_confirmer.length})</CardTitle>
          <CardDescription>
            Périodes dont le terme est atteint ou proche. Passé ce terme sans décision,
            l&apos;embauche est définitivement acquise.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.a_confirmer.length === 0 ? (
            <p className="text-sm text-muted-foreground">Rien à confirmer.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Contrat</TableHead>
                  <TableHead>Fin</TableHead>
                  <TableHead>Échéance</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.a_confirmer.map((trial: TrialPeriod) => {
                  const left = daysLeft(trial.end_date);
                  return (
                    <TableRow key={trial.id}>
                      <TableCell>
                        <Link className="hover:underline" to={`/employees/${trial.employee_id}`}>
                          {trial.employee_name || '—'}
                        </Link>
                      </TableCell>
                      <TableCell>
                        {trial.contract_type || '—'} · {trial.statut || '—'}
                      </TableCell>
                      <TableCell>{formatDate(trial.end_date)}</TableCell>
                      <TableCell>
                        <Badge variant={left < 0 ? 'destructive' : 'secondary'}>
                          {left < 0 ? `Dépassée de ${-left} j` : `J-${left}`}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          disabled={confirmMutation.isPending}
                          onClick={() => confirmMutation.mutate(trial.id)}
                        >
                          Confirmer l&apos;embauche
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>En cours ({data.en_cours.length})</CardTitle>
          <CardDescription>Périodes actives, hors fenêtre d&apos;alerte.</CardDescription>
        </CardHeader>
        <CardContent>
          {data.en_cours.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune période en cours.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Contrat</TableHead>
                  <TableHead>Début</TableHead>
                  <TableHead>Fin prévue</TableHead>
                  <TableHead>Renouvellement</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.en_cours.map((trial: TrialPeriod) => (
                  <TableRow key={trial.id}>
                    <TableCell>
                      <Link className="hover:underline" to={`/employees/${trial.employee_id}`}>
                        {trial.employee_name || '—'}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {trial.contract_type || '—'} · {trial.statut || '—'}
                    </TableCell>
                    <TableCell>{formatDate(trial.start_date)}</TableCell>
                    <TableCell>
                      {formatDate(trial.end_date)} · J-{daysLeft(trial.end_date)}
                    </TableCell>
                    <TableCell>
                      {trial.renewed_at
                        ? `Renouvelée le ${formatDate(trial.renewed_at)}`
                        : trial.renewal_allowed
                          ? 'Possible'
                          : 'Non prévu'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
          <div>
            <CardTitle>À qualifier ({data.a_qualifier.length})</CardTitle>
            <CardDescription>
              Salariés entrés il y a moins de huit mois sans période d&apos;essai enregistrée. Le
              barème société propose une durée ; elle reste modifiable depuis la fiche.
            </CardDescription>
          </div>
          <Button
            disabled={selected.size === 0 || applyMutation.isPending}
            onClick={() => applyMutation.mutate([...selected])}
          >
            {applyMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Appliquer le barème ({selected.size})
          </Button>
        </CardHeader>
        <CardContent>
          {data.a_qualifier.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Toutes les embauches récentes sont qualifiées.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10" />
                  <TableHead>Salarié</TableHead>
                  <TableHead>Contrat</TableHead>
                  <TableHead>Date d&apos;entrée</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.a_qualifier.map((emp: EmployeeToQualify) => (
                  <TableRow key={emp.id}>
                    <TableCell>
                      <Checkbox
                        checked={selected.has(emp.id)}
                        onCheckedChange={() => toggle(emp.id)}
                        aria-label={`Sélectionner ${emp.first_name} ${emp.last_name}`}
                      />
                    </TableCell>
                    <TableCell>
                      <Link className="hover:underline" to={`/employees/${emp.id}`}>
                        {`${emp.first_name} ${emp.last_name}`.trim()}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {emp.contract_type || '—'} · {emp.statut || '—'}
                    </TableCell>
                    <TableCell>{formatDate(emp.hire_date)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
