import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  acquitAlert,
  getComparison,
  ignoreAlert,
  type AlertLevel,
  type ComparisonResult,
  type PayslipAlert,
} from '@/api/payslips';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';

const MONTHS_SHORT = [
  'Jan',
  'Fév',
  'Mar',
  'Avr',
  'Mai',
  'Juin',
  'Juil',
  'Août',
  'Sep',
  'Oct',
  'Nov',
  'Déc',
];

export function formatMonthYearFr(month: number, year: number): string {
  const m = MONTHS_SHORT[month - 1] ?? String(month);
  return `${m} ${year}`;
}

export function formatEuro(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  return value.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
}

function lineRowClass(level: AlertLevel | null | undefined): string {
  if (level === 'CRITIQUE') return 'bg-red-50/90 dark:bg-red-950/30';
  if (level === 'AVERTISSEMENT') return 'bg-orange-50/90 dark:bg-orange-950/25';
  if (level === 'INFO') return 'bg-sky-50/80 dark:bg-sky-950/25';
  return '';
}

function countActiveByLevel(alerts: PayslipAlert[], level: AlertLevel): number {
  return alerts.filter((a) => a.level === level && a.status === 'active').length;
}

export interface PayslipComparisonTabProps {
  payslipId: string;
  isRH: boolean;
  onShowTrend: () => void;
  /** Après acquittement / ignore : re-synchroniser le bulletin parent (payslip_data, statut). */
  onPayslipRefresh?: () => void | Promise<void>;
}

export function PayslipComparisonTab({
  payslipId,
  isRH,
  onShowTrend,
  onPayslipRefresh,
}: PayslipComparisonTabProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const alertsRef = useRef<HTMLDivElement>(null);
  const [alertsOpen, setAlertsOpen] = useState(true);
  const [acquitRuleId, setAcquitRuleId] = useState<string | null>(null);
  const [acquitComment, setAcquitComment] = useState('');
  const [ignoreRuleId, setIgnoreRuleId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const comparisonQuery = useQuery({
    queryKey: ['payslip-comparison', payslipId],
    queryFn: () => getComparison(payslipId),
  });

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['payslip-comparison', payslipId] });
    await queryClient.invalidateQueries({ queryKey: ['payslip-trend', payslipId] });
    await queryClient.invalidateQueries({ queryKey: ['payslip-detail', payslipId] });
    await onPayslipRefresh?.();
  };

  const scrollToAlerts = () => {
    setAlertsOpen(true);
    requestAnimationFrame(() => {
      alertsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const handleAcquitSubmit = async () => {
    if (!acquitRuleId) return;
    setActionLoading(true);
    try {
      await acquitAlert(payslipId, acquitRuleId, acquitComment.trim() || undefined);
      toast({ title: 'Alerte acquittée' });
      setAcquitRuleId(null);
      setAcquitComment('');
      await invalidate();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? "Impossible d'acquitter",
        variant: 'destructive',
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleIgnoreConfirm = async () => {
    if (!ignoreRuleId) return;
    setActionLoading(true);
    try {
      await ignoreAlert(payslipId, ignoreRuleId);
      toast({ title: 'Alerte ignorée' });
      setIgnoreRuleId(null);
      await invalidate();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? "Impossible d'ignorer",
        variant: 'destructive',
      });
    } finally {
      setActionLoading(false);
    }
  };

  if (comparisonQuery.isLoading) {
    return (
      <div className="space-y-4 mt-6">
        <Skeleton className="h-10 w-full max-w-md" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (comparisonQuery.isError) {
    return (
      <Card className="mt-6 border-destructive/60 bg-destructive/5">
        <CardContent className="pt-6 flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
          <p className="text-sm text-destructive">
            Impossible de charger la comparaison. Vérifiez votre connexion ou réessayez plus tard.
          </p>
          <Button variant="outline" onClick={() => comparisonQuery.refetch()}>
            Réessayer
          </Button>
        </CardContent>
      </Card>
    );
  }

  const result = comparisonQuery.data as ComparisonResult;

  const crit = countActiveByLevel(result.alerts, 'CRITIQUE');
  const warn = countActiveByLevel(result.alerts, 'AVERTISSEMENT');
  const info = countActiveByLevel(result.alerts, 'INFO');

  return (
    <div className="space-y-6 mt-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold">
            Comparaison {formatMonthYearFr(result.month_n, result.year_n)}
            {result.bulletin_n1_id != null &&
            result.month_n1 != null &&
            result.year_n1 != null
              ? ` vs ${formatMonthYearFr(result.month_n1, result.year_n1)}`
              : ''}
          </h2>
          <p className="text-sm text-muted-foreground">
            Analyse automatique par rapport au dernier bulletin validé.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={scrollToAlerts}>
            <Badge variant="destructive" className="mr-1.5">
              {crit}
            </Badge>
            Critique
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={scrollToAlerts}>
            <Badge className="mr-1.5 bg-orange-500 hover:bg-orange-600">{warn}</Badge>
            Avertissement
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={scrollToAlerts}>
            <Badge className="mr-1.5 bg-sky-600 hover:bg-sky-700">{info}</Badge>
            Info
          </Button>
        </div>
      </div>

      {result.bulletin_n1_id == null ? (
        <Card className="border-sky-200 bg-sky-50/60 dark:bg-sky-950/20">
          <CardContent className="py-4 text-sm">
            Aucun bulletin N-1 disponible pour ce salarié.
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Tableau comparatif</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Poste</TableHead>
                <TableHead className="text-right">N</TableHead>
                <TableHead className="text-right">N-1</TableHead>
                <TableHead className="text-right">Δ abs.</TableHead>
                <TableHead className="text-right">Δ %</TableHead>
                <TableHead>Niveau</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.lines.map((line) => (
                <TableRow key={line.libelle} className={lineRowClass(line.alert_level)}>
                  <TableCell className="font-medium">{line.libelle}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatEuro(line.value_n)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatEuro(line.value_n1)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {line.delta_abs === null || line.delta_abs === undefined
                      ? '—'
                      : formatEuro(line.delta_abs)}
                  </TableCell>
                  <TableCell
                    className={cn(
                      'text-right tabular-nums font-medium',
                      line.delta_pct != null &&
                        line.delta_pct < 0 &&
                        'text-red-600 dark:text-red-400',
                      line.delta_pct != null &&
                        line.delta_pct > 0 &&
                        'text-emerald-600 dark:text-emerald-400'
                    )}
                  >
                    {line.delta_pct === null || line.delta_pct === undefined
                      ? '—'
                      : `${line.delta_pct.toFixed(2)} %`}
                  </TableCell>
                  <TableCell>
                    {line.alert_level ? (
                      <Badge
                        variant={line.alert_level === 'CRITIQUE' ? 'destructive' : 'secondary'}
                        className={cn(
                          line.alert_level === 'AVERTISSEMENT' && 'bg-orange-500 text-white',
                          line.alert_level === 'INFO' && 'bg-sky-600 text-white'
                        )}
                      >
                        {line.alert_level}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Collapsible open={alertsOpen} onOpenChange={setAlertsOpen}>
        <Card ref={alertsRef}>
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer select-none flex flex-row items-center justify-between space-y-0 py-4">
              <CardTitle className="text-base">
                Alertes détectées ({result.alerts.length})
              </CardTitle>
              {alertsOpen ? (
                <ChevronDown className="h-5 w-5 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-5 w-5 text-muted-foreground" />
              )}
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent className="space-y-4 pt-0">
              {result.alerts.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune alerte.</p>
              ) : (
                result.alerts.map((alert) => (
                  <AlertRow
                    key={`${alert.rule_id}-${alert.message.slice(0, 40)}`}
                    alert={alert}
                    isRH={isRH}
                    onAcquit={() => setAcquitRuleId(alert.rule_id)}
                    onIgnore={() => setIgnoreRuleId(alert.rule_id)}
                  />
                ))
              )}
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      <div className="flex justify-end">
        <Button type="button" variant="link" onClick={onShowTrend}>
          Voir la tendance
        </Button>
      </div>

      <Dialog open={!!acquitRuleId} onOpenChange={(o) => !o && setAcquitRuleId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Acquitter l’alerte</DialogTitle>
          </DialogHeader>
          <Textarea
            placeholder="Commentaire optionnel…"
            value={acquitComment}
            onChange={(e) => setAcquitComment(e.target.value)}
            rows={3}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setAcquitRuleId(null)}>
              Annuler
            </Button>
            <Button onClick={handleAcquitSubmit} disabled={actionLoading}>
              {actionLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Confirmer'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!ignoreRuleId} onOpenChange={(o) => !o && setIgnoreRuleId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Ignorer cette alerte ?</AlertDialogTitle>
            <AlertDialogDescription>
              L’alerte sera marquée comme ignorée. Vous pourrez toujours consulter l’historique côté
              bulletin.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={handleIgnoreConfirm} disabled={actionLoading}>
              Ignorer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function AlertRow({
  alert,
  isRH,
  onAcquit,
  onIgnore,
}: {
  alert: PayslipAlert;
  isRH: boolean;
  onAcquit: () => void;
  onIgnore: () => void;
}) {
  const levelBadge =
    alert.level === 'CRITIQUE' ? (
      <Badge variant="destructive">{alert.level}</Badge>
    ) : alert.level === 'AVERTISSEMENT' ? (
      <Badge className="bg-orange-500 text-white">{alert.level}</Badge>
    ) : (
      <Badge className="bg-sky-600 text-white">{alert.level}</Badge>
    );

  return (
    <div className="rounded-lg border p-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {levelBadge}
        <span className="text-xs text-muted-foreground font-mono">{alert.rule_id}</span>
        {alert.status === 'acquittee' ? (
          <Badge className="bg-emerald-600 text-white">Acquittée</Badge>
        ) : null}
        {alert.status === 'ignoree' ? (
          <Badge variant="secondary">Ignorée</Badge>
        ) : null}
      </div>
      <p className="text-sm">{alert.message}</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-sm">
        <div>
          <span className="text-muted-foreground">Valeur N</span>
          <p className="font-medium tabular-nums">{formatEuro(alert.value_n)}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Valeur N-1</span>
          <p className="font-medium tabular-nums">{formatEuro(alert.value_n1)}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Variation</span>
          <p
            className={cn(
              'font-medium tabular-nums',
              alert.delta_pct < 0 && 'text-red-600',
              alert.delta_pct > 0 && 'text-emerald-600'
            )}
          >
            {alert.delta_pct.toFixed(2)} %
          </p>
        </div>
      </div>
      {alert.status === 'acquittee' && (
        <p className="text-xs text-muted-foreground">
          {alert.acquitted_by ? `Par ${alert.acquitted_by}` : ''}
          {alert.acquitted_at ? ` · ${alert.acquitted_at}` : ''}
          {alert.comment ? ` · ${alert.comment}` : ''}
        </p>
      )}
      {alert.status === 'ignoree' && (
        <p className="text-xs text-muted-foreground">
          {alert.acquitted_by ? `Par ${alert.acquitted_by}` : ''}
          {alert.acquitted_at ? ` · ${alert.acquitted_at}` : ''}
          {alert.comment ? ` · ${alert.comment}` : ''}
        </p>
      )}
      {alert.status === 'active' && isRH ? (
        <div className="flex gap-2 pt-1">
          <Button size="sm" variant="secondary" onClick={onAcquit}>
            Acquitter
          </Button>
          <Button size="sm" variant="outline" onClick={onIgnore}>
            Ignorer
          </Button>
        </div>
      ) : null}
    </div>
  );
}
