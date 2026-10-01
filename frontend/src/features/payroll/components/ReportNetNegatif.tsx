import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ArrowRight, Check, Loader2 } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { getReportNetNegatif } from '@/api/payslips';
import {
  createEmployeeMonthlyInput,
  deleteEmployeeMonthlyInput,
  updateMonthlyInput,
} from '@/api/saisies';
import { queryKeys } from '@/lib/queryKeys';
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
  /** Liste : seule une ligne à net négatif interroge le serveur. */
  netAPayer?: number | null;
  /** Éditeur : toujours interroger (un report peut survivre à un net redevenu positif). */
  toujours?: boolean;
  variante: 'ligne' | 'editeur';
};

const API = {
  creer: createEmployeeMonthlyInput,
  mettreAJour: updateMonthlyInput,
  supprimer: deleteEmployeeMonthlyInput,
};

/** Propose de reporter un net négatif sur le mois suivant, en un clic. */
export function ReportNetNegatif({ payslipId, companyId, netAPayer, toujours = false, variante }: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const actif = toujours || (netAPayer != null && netAPayer < 0);

  const { data: etat } = useQuery({
    queryKey: queryKeys.reportNetNegatif(companyId, payslipId),
    queryFn: () => getReportNetNegatif(payslipId, companyId),
    enabled: actif,
    staleTime: 30_000,
  });

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
    if (bouton) return bouton;
    return (
      <Button variant="ghost" size="sm" asChild title="Ouvrir les saisies du mois suivant">
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
      <AlertTitle>Net à payer négatif</AlertTitle>
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
