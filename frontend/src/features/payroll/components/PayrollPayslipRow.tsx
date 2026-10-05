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
import { MOTIF_BULLETIN_IMPORTE, estBulletinImporte } from '@/features/payroll/utils/bulletinImporte';
import { estPerime } from '@/features/payroll/utils/bulletinARecalculer';
import {
  hasNetSuperieurBrutWarning,
  isNetSuperieurBrutWarning,
  normalizePayslipWarning,
  PayslipNetBrutInlineLabel,
} from '@/lib/payslipNetBrutAlert';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { ReportNetNegatif } from '@/features/payroll/components/ReportNetNegatif';
import { libelleDuBlocage } from '@/features/payroll/utils/employmentPeriod';
import { useGenerationEnCours } from '@/features/payroll/components/GenerationEnCoursContext';
import { Edit, Loader2, Trash2, AlertTriangle, RefreshCw } from 'lucide-react';

export type PayslipRowStatus = 'idle' | 'loading' | 'success' | 'error' | 'unavailable';

export type PayslipRowState = {
  status: PayslipRowStatus;
  payslip?: PayslipInfo;
  errorMessage?: string;
  warnings?: string[];
};

/** Écart avec le mois précédent, déjà dit (vue par mois). */
export type EcartLigne = {
  /** « +3 % sur août » ; null sans mois précédent. */
  texte: string | null;
  fort: boolean;
  /** Ce qui met la ligne en orange (« Net +14 % sur août · 22 h sup. »). */
  raison: string | null;
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
  /** Écart avec le mois précédent (vue par mois). */
  ecart?: EcartLigne | null;
};

function formatEuro(montant?: number | null): string | null {
  if (montant == null || Number.isNaN(montant)) return null;
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(montant);
}

export function PayrollPayslipRow({
  name,
  state,
  onGenerate,
  onDelete,
  deletingPayslipId,
  deleteDescription,
  ecart,
}: PayrollPayslipRowProps) {
  const payslip = state.payslip;
  const netLabel = payslip ? formatEuro(payslip.net_a_payer) : null;
  const brutLabel = payslip ? formatEuro(payslip.salaire_brut) : null;
  const ecartAffiche = ecart ? (ecart.fort ? ecart.raison : ecart.texte) : null;
  const warnings = state.warnings ?? payslip?.warnings ?? [];
  const showNetBrut = hasNetSuperieurBrutWarning(warnings);
  const otherWarnings = warnings
    .filter((w) => !isNetSuperieurBrutWarning(w))
    .map(normalizePayslipWarning);
  const firstOtherWarning = otherWarnings[0];
  // Points à arbitrer (plafond transport…) : le bulletin est bon, la RH a une
  // décision à prendre. Pas une alerte : un badge gris, le détail au survol.
  const pointsAArbitrer = payslip?.points_a_arbitrer ?? [];
  // Bulletin repris de l'ancien logiciel : les actions restent visibles mais
  // grisées, le motif au survol (demande d'Alexandre, 21/09).
  const importe = estBulletinImporte(payslip);
  const perime = estPerime(payslip);
  const companyId = useActiveCompanyId();
  const generationEnCours = useGenerationEnCours();
  const motifGeneration = generationEnCours ? 'Génération en cours : patientez' : undefined;
  const netNegatif = (payslip?.net_a_payer ?? 0) < 0;
  const valide = payslip?.status === 'valide';
  const enAlerte = warnings.length > 0 || netNegatif;
  const badgeValide = (
    <Badge className="bg-emerald-600 text-white hover:bg-emerald-600" data-testid="badge-valide">
      Validé
    </Badge>
  );

  const statusBadge =
    state.status === 'success' ? (
      enAlerte ? (
        <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">
          <AlertTriangle className="mr-1 h-3 w-3" aria-hidden />
          Alerte
        </Badge>
      ) : valide ? (
        badgeValide
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
    ) : state.status === 'unavailable' ? (
      <Badge variant="outline" className="text-muted-foreground">
        {libelleDuBlocage(state.errorMessage ?? '')}
      </Badge>
    ) : (
      <Badge variant="outline" className="text-muted-foreground">
        À générer
      </Badge>
    );

  const meta = (
    <>
      {statusBadge}
      {state.status === 'success' && enAlerte && valide ? badgeValide : null}
      {importe && (
        <Badge variant="outline" className="text-muted-foreground" title={MOTIF_BULLETIN_IMPORTE}>
          Importé
        </Badge>
      )}
      {perime && (
        <Badge
          variant="outline"
          className="border-amber-200 bg-amber-50 text-amber-800"
          data-testid="badge-a-recalculer"
          title={payslip?.raison_a_recalculer ?? undefined}
        >
          À recalculer
        </Badge>
      )}
      {state.status === 'success' && pointsAArbitrer.length > 0 && (
        <Badge
          variant="outline"
          className="text-muted-foreground"
          title={pointsAArbitrer.join(' · ')}
        >
          À arbitrer
        </Badge>
      )}
      {(brutLabel || netLabel) && (
        <span className="text-xs text-muted-foreground tabular-nums">
          {[brutLabel && `Brut ${brutLabel}`, netLabel && `Net ${netLabel}`]
            .filter(Boolean)
            .join(' · ')}
        </span>
      )}
      {state.status === 'success' && ecartAffiche && (
        <span
          className={
            ecart?.fort
              ? 'text-xs font-medium tabular-nums text-amber-700 dark:text-amber-400'
              : 'text-xs tabular-nums text-muted-foreground'
          }
          data-testid="ecart-mois-precedent"
        >
          {ecartAffiche}
        </span>
      )}
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
  } else if (state.status === 'unavailable') {
    actions = null;
  } else if (state.status === 'success' && payslip) {
    actions = (
      <>
        <ViewLinkButton href={payslip.preview_url ?? payslip.url ?? ''} title="Visualiser le bulletin" downloadUrl={payslip.url} downloadName={payslip.name} />
        {importe || generationEnCours ? (
          <Button variant="outline" size="sm" disabled title={importe ? MOTIF_BULLETIN_IMPORTE : motifGeneration}>
            <Edit className="mr-2 h-4 w-4" />
            Modifier
          </Button>
        ) : (
          <Button variant="outline" size="sm" asChild>
            <Link to={`/payslips/${payslip.id}/edit`}>
              <Edit className="mr-2 h-4 w-4" />
              Modifier
            </Link>
          </Button>
        )}
        {perime ? (
          <Button
            size="sm"
            variant="outline"
            onClick={onGenerate}
            disabled={generationEnCours}
            title={motifGeneration}
            data-testid="recalculer-ligne"
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Recalculer
          </Button>
        ) : null}
        <ReportNetNegatif
          payslipId={payslip.id}
          companyId={companyId}
          variante="ligne"
        />
        <DownloadLinkButton href={payslip.url} download={payslip.name} label="Télécharger" />
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-destructive hover:text-destructive"
              disabled={deletingPayslipId === payslip.id || importe || generationEnCours}
              title={importe ? MOTIF_BULLETIN_IMPORTE : motifGeneration}
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
      <Button size="sm" variant="destructive" onClick={onGenerate} disabled={generationEnCours} title={motifGeneration}>
        Réessayer
      </Button>
    );
  } else {
    actions = (
      <Button size="sm" variant="outline" onClick={onGenerate} disabled={generationEnCours} title={motifGeneration}>
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
      rowHref={state.status === 'success' && payslip && !generationEnCours ? `/payslips/${payslip.id}/edit` : undefined}
      subtitle={
        state.status === 'error' && state.errorMessage ? (
          <span className="text-destructive">{state.errorMessage}</span>
        ) : state.status === 'unavailable' && state.errorMessage ? (
          <span className="text-muted-foreground">{state.errorMessage}</span>
        ) : firstOtherWarning ? (
          <span className="text-amber-700 dark:text-amber-400">{firstOtherWarning}</span>
        ) : state.status === 'success' && pointsAArbitrer.length > 0 ? (
          // Point à arbitrer : lisible sans survol, en gris, une ligne.
          <span className="text-muted-foreground">{pointsAArbitrer[0]}</span>
        ) : undefined
      }
      meta={meta}
      actions={actions}
    />
  );
}
