import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { PreflightAnomaly, PreflightResolutionMotif } from '@/api/payrollPreflight';
import {
  PREFLIGHT_ANOMALY_TYPE_LABELS,
  PREFLIGHT_RESOLUTION_MOTIF_LABELS,
} from '@/features/payroll/components/review/preflightLabels';

interface JustifyAnomalyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  anomalies: PreflightAnomaly[];
  onConfirm: (motif: PreflightResolutionMotif, commentaire: string) => Promise<void>;
  isSubmitting?: boolean;
}

export function JustifyAnomalyDialog({
  open,
  onOpenChange,
  anomalies,
  onConfirm,
  isSubmitting = false,
}: JustifyAnomalyDialogProps) {
  const [motif, setMotif] = useState<PreflightResolutionMotif>('directeur_site');
  const [commentaire, setCommentaire] = useState('');

  useEffect(() => {
    if (!open) return;
    setMotif('directeur_site');
    setCommentaire('');
  }, [open, anomalies]);

  const requiresComment = motif === 'autre';
  const canSubmit = !requiresComment || commentaire.trim().length > 0;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    await onConfirm(motif, commentaire.trim());
  };

  const title =
    anomalies.length > 1
      ? `Justifier ${anomalies.length} anomalies`
      : 'Justifier l\'anomalie';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        {anomalies.length === 1 && (
          <p className="text-sm text-muted-foreground">
            {anomalies[0].employee_name} — {PREFLIGHT_ANOMALY_TYPE_LABELS[anomalies[0].type]}
          </p>
        )}

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="preflight-motif">Motif</Label>
            <Select
              value={motif}
              onValueChange={(value) => setMotif(value as PreflightResolutionMotif)}
            >
              <SelectTrigger id="preflight-motif">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(PREFLIGHT_RESOLUTION_MOTIF_LABELS) as PreflightResolutionMotif[]).map(
                  (key) => (
                    <SelectItem key={key} value={key}>
                      {PREFLIGHT_RESOLUTION_MOTIF_LABELS[key]}
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="preflight-commentaire">
              Commentaire{requiresComment ? ' (obligatoire)' : ' (optionnel)'}
            </Label>
            <Textarea
              id="preflight-commentaire"
              value={commentaire}
              onChange={(e) => setCommentaire(e.target.value)}
              placeholder={
                motif === 'directeur_site'
                  ? 'Nom du directeur, date de validation…'
                  : 'Précisez le contexte…'
              }
              rows={3}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            Annuler
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit || isSubmitting}>
            {isSubmitting ? 'Enregistrement…' : 'Justifier'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
