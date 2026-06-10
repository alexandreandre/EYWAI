import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { DocumentFileRow, DownloadLinkButton, ViewLinkButton } from '@/components/employee-detail/DocumentFileRow';
import type { PayslipInfo } from '@/api/payslips';
import {
  hasNetSuperieurBrutWarning,
  isNetSuperieurBrutWarning,
  normalizePayslipWarning,
  PayslipNetBrutInlineLabel,
} from '@/lib/payslipNetBrutAlert';
import { Edit, Loader2, Trash2, AlertTriangle } from 'lucide-react';

export type PayslipRowStatus = 'idle' | 'loading' | 'success' | 'error';

export type PayslipRowState = {
  status: PayslipRowStatus;
  payslip?: PayslipInfo;
  errorMessage?: string;
  warnings?: string[];
};

type PayrollPayslipRowProps = {
  /** Libellé principal de la ligne (mois ou nom du collaborateur). */
  name: string;
  state: PayslipRowState;
  onGenerate: () => void;
  onDelete: (payslipId: string) => void;
  deletingPayslipId: string | null;
  /** Texte affiché dans la confirmation de suppression. */
  deleteDescription: ReactNode;
};

function formatNet(net?: number): string | null {
  if (net == null || Number.isNaN(net)) return null;
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(net);
}

export function PayrollPayslipRow({
  name,
  state,
  onGenerate,
  onDelete,
  deletingPayslipId,
  deleteDescription,
}: PayrollPayslipRowProps) {
  const payslip = state.payslip;
  const netLabel = payslip ? formatNet(payslip.net_a_payer) : null;
  const warnings = state.warnings ?? payslip?.warnings ?? [];
  const showNetBrut = hasNetSuperieurBrutWarning(warnings);
  const otherWarnings = warnings
    .filter((w) => !isNetSuperieurBrutWarning(w))
    .map(normalizePayslipWarning);
  const firstOtherWarning = otherWarnings[0];

  const statusBadge =
    state.status === 'success' ? (
      warnings.length > 0 ? (
        <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">
          <AlertTriangle className="mr-1 h-3 w-3" aria-hidden />
          Alerte
        </Badge>
      ) : (
        <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-800">
          Généré
        </Badge>
      )
    ) : state.status === 'loading' ? (
      <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-800">
        En cours…
      </Badge>
    ) : state.status === 'error' ? (
      <Badge variant="outline" className="border-red-200 bg-red-50 text-red-800">
        Échec
      </Badge>
    ) : (
      <Badge variant="outline" className="text-muted-foreground">
        À générer
      </Badge>
    );

  const meta = (
    <>
      {statusBadge}
      {netLabel && <span className="text-xs text-muted-foreground">Net {netLabel}</span>}
      {payslip?.manually_edited && (
        <Badge variant="secondary" className="text-xs">
          Modifié
        </Badge>
      )}
    </>
  );

  let actions: ReactNode;
  if (state.status === 'loading') {
    actions = <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />;
  } else if (state.status === 'success' && payslip) {
    actions = (
      <>
        <ViewLinkButton href={payslip.preview_url ?? ''} title="Visualiser le bulletin" />
        <Button variant="outline" size="sm" asChild>
          <Link to={`/payslips/${payslip.id}/edit`}>
            <Edit className="mr-2 h-4 w-4" />
            Modifier
          </Link>
        </Button>
        <DownloadLinkButton href={payslip.url} download={payslip.name} label="Télécharger" />
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-destructive hover:text-destructive"
              disabled={deletingPayslipId === payslip.id}
            >
              {deletingPayslipId === payslip.id ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              <span className="sr-only">Supprimer</span>
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Supprimer ce bulletin ?</AlertDialogTitle>
              <AlertDialogDescription>{deleteDescription}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Annuler</AlertDialogCancel>
              <AlertDialogAction onClick={() => onDelete(payslip.id)}>Supprimer</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </>
    );
  } else if (state.status === 'error') {
    actions = (
      <Button size="sm" variant="destructive" onClick={onGenerate}>
        Réessayer
      </Button>
    );
  } else {
    actions = (
      <Button size="sm" variant="outline" onClick={onGenerate}>
        Générer
      </Button>
    );
  }

  return (
    <DocumentFileRow
      name={
        <>
          {name}
          {showNetBrut ? <PayslipNetBrutInlineLabel /> : null}
        </>
      }
      rowHref={state.status === 'success' && payslip ? `/payslips/${payslip.id}/edit` : undefined}
      subtitle={
        state.status === 'error' && state.errorMessage ? (
          <span className="text-destructive">{state.errorMessage}</span>
        ) : firstOtherWarning ? (
          <span className="text-amber-700 dark:text-amber-400">{firstOtherWarning}</span>
        ) : undefined
      }
      meta={meta}
      actions={actions}
    />
  );
}
