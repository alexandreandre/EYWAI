import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ArrowRight, Check, Loader2 } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import {
  executerReportNetNegatif,
  getReportNetNegatif,
  getReportsNetNegatifDuMois,
  type EtatReportNetNegatif,
} from '@/api/payslips';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { invaliderCles } from '@/features/payroll/utils/invalidationsBulletin';
import {
  clesApresReport,
  executerReport,
  messageEchecReport,
  messageSuccesReport,
  vueDuReport,
  type ActionReport,
} from '@/features/payroll/utils/reportNetNegatif';

type Props = {
  payslipId: string;
  /** Société du bulletin : lectures et écritures partent avec elle. */
  companyId: string | undefined;
  variante: 'ligne' | 'editeur';
};

const API = {
  executer: executerReportNetNegatif,
};

/** Lot du mois de paie : une lecture, pas une requête par salarié. */
const LotReportsNetNegatif = createContext<Record<string, EtatReportNetNegatif> | null>(null);

export function ReportsNetNegatifDuMois({
  year,
  month,
  children,
}: {
  year: number;
  month: number;
  children: ReactNode;
}) {
  const companyId = useActiveCompanyId();
  const { data } = useQuery({
    queryKey: queryKeys.reportsNetNegatifDuMois(companyId, year, month),
    queryFn: () => getReportsNetNegatifDuMois(year, month, companyId),
    enabled: Boolean(companyId),
    staleTime: 30_000,
  });
  const parId = useMemo(() => {
    const map: Record<string, EtatReportNetNegatif> = {};
    for (const etat of data ?? []) map[etat.payslip_id] = etat;
    return map;
  }, [data]);
  return <LotReportsNetNegatif.Provider value={parId}>{children}</LotReportsNetNegatif.Provider>;
}

/** Propose de reporter un net négatif sur le mois suivant, en un clic. */
export function ReportNetNegatif({ payslipId, companyId, variante }: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const lot = useContext(LotReportsNetNegatif);
  const depuisLot = lot !== null;

  const { data: etatSeul } = useQuery({
    queryKey: queryKeys.reportNetNegatif(companyId, payslipId),
    queryFn: () => getReportNetNegatif(payslipId, companyId),
    enabled: !depuisLot && Boolean(payslipId),
    staleTime: 30_000,
  });

  const etat = depuisLot ? lot[payslipId] : etatSeul;

  const mutation = useMutation({
    mutationFn: (action: ActionReport) => executerReport(action, etat!, API),
    onSuccess: (_, action) => toast({ title: messageSuccesReport(action, etat!) }),
    onError: (erreur, action) =>
      toast({
        variant: 'destructive',
        title: 'Report du net négatif',
        description: messageEchecReport(action, erreur),
      }),
    onSettled: () => invaliderCles(queryClient, clesApresReport(companyId, etat!.employee_id)),
  });

  if (!etat) return null;
  const vue = vueDuReport(etat);
  if (!vue.visible) return null;

  const action = vue.action;
  const bouton =
    action && vue.bouton ? (
      <Button
        type="button"
        size="sm"
        variant={action === 'supprimer' ? 'outline' : 'default'}
        disabled={vue.desactive || mutation.isPending}
        title={vue.explication ?? (variante === 'ligne' ? vue.texte : undefined)}
        data-testid="report-net-negatif"
        onClick={() => mutation.mutate(action)}
      >
        {mutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
        {vue.bouton}
      </Button>
    ) : null;

  if (variante === 'ligne') {
    if (action === 'supprimer' && bouton) {
      return (
        <span className="inline-flex max-w-md flex-wrap items-center gap-2">
          <span className="text-xs text-amber-800" title={vue.explication ?? vue.texte}>
            {vue.texte}
          </span>
          {bouton}
        </span>
      );
    }
    if (bouton) return bouton;
    return (
      <Button
        variant="ghost"
        size="sm"
        asChild
        title={vue.explication ?? 'Ouvrir les saisies du mois suivant'}
      >
        <Link to={vue.lien ?? '/saisies'} data-testid="report-net-negatif-fait">
          <Check className="mr-1 h-4 w-4 text-emerald-600" aria-hidden />
          {vue.texte}
        </Link>
      </Button>
    );
  }

  return (
    <Alert data-testid="report-net-negatif-encart">
      <AlertTriangle className="h-4 w-4" aria-hidden />
      <AlertTitle>
        {etat.montant_a_reporter > 0 ? 'Net à payer négatif' : 'Report du net négatif'}
      </AlertTitle>
      <AlertDescription className="space-y-2">
        <p>{vue.texte}</p>
        {vue.explication ? <p className="text-muted-foreground">{vue.explication}</p> : null}
        <div className="flex flex-wrap items-center gap-2">
          {bouton}
          {vue.lien ? (
            <Button variant="link" size="sm" className="px-0" asChild>
              <Link to={vue.lien}>
                Voir les saisies du mois suivant
                <ArrowRight className="ml-1 h-4 w-4" aria-hidden />
              </Link>
            </Button>
          ) : null}
        </div>
      </AlertDescription>
    </Alert>
  );
}
