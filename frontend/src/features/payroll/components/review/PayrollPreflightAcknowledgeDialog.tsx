import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { AlertTriangle } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { PreflightAnomaliesResponse } from '@/api/payrollPreflight';
import { PREFLIGHT_ANOMALY_TYPE_LABELS } from '@/features/payroll/components/review/preflightLabels';

interface PayrollPreflightAcknowledgeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  data: PreflightAnomaliesResponse | undefined;
  acknowledged: boolean;
  onAcknowledgedChange: (checked: boolean) => void;
  onConfirm: () => void;
  isSubmitting?: boolean;
}

export function PayrollPreflightAcknowledgeDialog({
  open,
  onOpenChange,
  data,
  acknowledged,
  onAcknowledgedChange,
  onConfirm,
  isSubmitting = false,
}: PayrollPreflightAcknowledgeDialogProps) {
  const openCount = data?.total_open ?? 0;
  const counts = data?.counts;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-600" aria-hidden />
            Lancer la paie avec des réserves
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3 text-sm">
          <p>
            {openCount} anomalie{openCount > 1 ? 's' : ''} non traitée
            {openCount > 1 ? 's' : ''} pour ce mois.
          </p>
          {counts && (
            <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
              {counts.ecart_heures > 0 && (
                <li>
                  {counts.ecart_heures} {PREFLIGHT_ANOMALY_TYPE_LABELS.ecart_heures.toLowerCase()}
                </li>
              )}
              {counts.heures_non_saisies > 0 && (
                <li>
                  {counts.heures_non_saisies}{' '}
                  {PREFLIGHT_ANOMALY_TYPE_LABELS.heures_non_saisies.toLowerCase()}
                </li>
              )}
              {counts.pointage > 0 && (
                <li>
                  {counts.pointage} {PREFLIGHT_ANOMALY_TYPE_LABELS.pointage.toLowerCase()}
                </li>
              )}
              {counts.conflit_absence > 0 && (
                <li>
                  {counts.conflit_absence}{' '}
                  {PREFLIGHT_ANOMALY_TYPE_LABELS.conflit_absence.toLowerCase()}
                </li>
              )}
            </ul>
          )}
          <p className="text-muted-foreground">
            Vous pouvez continuer, mais nous vous recommandons de traiter ou justifier ces points
            avant la génération des bulletins.
          </p>
          <Link
            to="/payroll/review"
            className="inline-block text-sm font-medium text-cyan-600 hover:underline"
            onClick={() => onOpenChange(false)}
          >
            Revoir les anomalies
          </Link>
        </div>

        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-500/30 dark:bg-amber-950/20">
          <Checkbox
            id="preflight-ack"
            checked={acknowledged}
            onCheckedChange={(checked) => onAcknowledgedChange(checked === true)}
          />
          <Label htmlFor="preflight-ack" className="text-sm font-normal leading-snug">
            J&apos;ai pris connaissance des anomalies restantes et j&apos;assume le lancement de la
            paie malgré ces réserves.
          </Label>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            Annuler
          </Button>
          <Button
            className="bg-cyan-500 hover:bg-cyan-600 text-white"
            onClick={onConfirm}
            disabled={!acknowledged || isSubmitting}
          >
            {isSubmitting ? 'Enregistrement…' : 'Lancer quand même'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
