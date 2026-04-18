import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { acquitAlert, getComparison, ignoreAlert, validatePayslip } from '@/api/payslips';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Loader2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
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

export interface PayslipValidateBlockedModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  payslipId: string;
  isRH: boolean;
  onValidated: () => void | Promise<void>;
}

export function PayslipValidateBlockedModal({
  open,
  onOpenChange,
  payslipId,
  isRH,
  onValidated,
}: PayslipValidateBlockedModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [acquitRuleId, setAcquitRuleId] = useState<string | null>(null);
  const [acquitComment, setAcquitComment] = useState('');
  const [ignoreRuleId, setIgnoreRuleId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const comparisonQuery = useQuery({
    queryKey: ['payslip-comparison', payslipId],
    queryFn: () => getComparison(payslipId),
    enabled: open && !!payslipId,
  });

  const activeCritical = useMemo(() => {
    const alerts = comparisonQuery.data?.alerts ?? [];
    return alerts.filter((a) => a.level === 'CRITIQUE' && a.status === 'active');
  }, [comparisonQuery.data]);

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['payslip-comparison', payslipId] });
    await queryClient.invalidateQueries({ queryKey: ['payslip-trend', payslipId] });
    await comparisonQuery.refetch();
  };

  const handleAcquit = async () => {
    if (!acquitRuleId) return;
    setBusy(true);
    try {
      await acquitAlert(payslipId, acquitRuleId, acquitComment.trim() || undefined);
      setAcquitRuleId(null);
      setAcquitComment('');
      toast({ title: 'Alerte acquittée' });
      await invalidate();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? "Impossible d'acquitter",
        variant: 'destructive',
      });
    } finally {
      setBusy(false);
    }
  };

  const handleIgnore = async () => {
    if (!ignoreRuleId) return;
    setBusy(true);
    try {
      await ignoreAlert(payslipId, ignoreRuleId);
      setIgnoreRuleId(null);
      toast({ title: 'Alerte ignorée' });
      await invalidate();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? "Impossible d'ignorer",
        variant: 'destructive',
      });
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmValidate = async () => {
    if (activeCritical.length > 0) return;
    setBusy(true);
    try {
      await validatePayslip(payslipId);
      toast({ title: 'Bulletin validé' });
      onOpenChange(false);
      await onValidated();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: unknown } } };
      toast({
        title: 'Erreur',
        description: typeof err.response?.data?.detail === 'string' ? err.response.data.detail : 'Échec de la validation',
        variant: 'destructive',
      });
      await invalidate();
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Validation impossible — alertes critiques non traitées</DialogTitle>
          </DialogHeader>
          {comparisonQuery.isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <ul className="space-y-4 text-sm">
              {activeCritical.length === 0 ? (
                <p className="text-muted-foreground">
                  Toutes les alertes critiques sont traitées. Vous pouvez confirmer la validation.
                </p>
              ) : (
                activeCritical.map((a) => (
                  <li key={a.rule_id + a.message} className="rounded-md border p-3 space-y-2">
                    <div className="flex flex-wrap gap-2 items-center">
                      <Badge variant="destructive">{a.level}</Badge>
                      <span className="font-mono text-xs">{a.rule_id}</span>
                    </div>
                    <p>{a.message}</p>
                    {isRH ? (
                      <div className="flex gap-2 pt-1">
                        <Button size="sm" variant="secondary" onClick={() => setAcquitRuleId(a.rule_id)}>
                          Acquitter
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setIgnoreRuleId(a.rule_id)}>
                          Ignorer
                        </Button>
                      </div>
                    ) : null}
                  </li>
                ))
              )}
            </ul>
          )}
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button
              onClick={handleConfirmValidate}
              disabled={busy || activeCritical.length > 0 || comparisonQuery.isLoading}
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Confirmer la validation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!acquitRuleId} onOpenChange={(o) => !o && setAcquitRuleId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Acquitter l’alerte</DialogTitle>
          </DialogHeader>
          <Textarea
            value={acquitComment}
            onChange={(e) => setAcquitComment(e.target.value)}
            placeholder="Commentaire optionnel…"
            rows={3}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setAcquitRuleId(null)}>
              Annuler
            </Button>
            <Button onClick={handleAcquit} disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Confirmer'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!ignoreRuleId} onOpenChange={(o) => !o && setIgnoreRuleId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Ignorer cette alerte ?</AlertDialogTitle>
            <AlertDialogDescription>
              L’alerte sera marquée comme ignorée pour la validation.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={handleIgnore} disabled={busy}>
              Ignorer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
