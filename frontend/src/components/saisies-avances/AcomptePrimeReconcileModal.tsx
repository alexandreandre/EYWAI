import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { Loader2 } from 'lucide-react';
import { reconcileAcomptePrime } from '@/api/saisiesAvances';
import type { SalaryAdvance } from '@/api/saisiesAvances';
import { formatCurrency } from '@/lib/employeeDashboardUtils';
import { getAdvanceTypeLabel } from '@/lib/employeeSalaryAdvancesUtils';

interface AcomptePrimeReconcileModalProps {
  advance: SalaryAdvance;
  onClose: () => void;
  onSuccess: () => void;
}

export function AcomptePrimeReconcileModal({
  advance,
  onClose,
  onSuccess,
}: AcomptePrimeReconcileModalProps) {
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const today = new Date();
  const [primeFinalAmount, setPrimeFinalAmount] = useState(
    advance.prime_expected_amount != null
      ? String(advance.prime_expected_amount)
      : ''
  );
  const [year, setYear] = useState(String(today.getFullYear()));
  const [month, setMonth] = useState(String(today.getMonth() + 1));

  const acompteVerse = Number(advance.approved_amount || advance.requested_amount || 0);
  const solde =
    primeFinalAmount.trim() !== ''
      ? Math.max(0, Number(primeFinalAmount) - acompteVerse)
      : null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const finalAmount = Number(primeFinalAmount);
    if (!finalAmount || finalAmount <= 0) {
      toast({
        title: 'Erreur',
        description: 'Indiquez le montant définitif de la prime.',
        variant: 'destructive',
      });
      return;
    }

    setIsLoading(true);
    try {
      await reconcileAcomptePrime(advance.id, {
        prime_final_amount: finalAmount,
        year: Number(year),
        month: Number(month),
      });
      toast({
        title: 'Succès',
        description: 'Acompte sur prime réconcilié. Le solde sera déduit sur le bulletin choisi.',
      });
      onSuccess();
    } catch (error: unknown) {
      const detail =
        error && typeof error === 'object' && 'response' in error
          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: 'Erreur',
        description: detail || 'Impossible de réconcilier l’acompte sur prime.',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Solder l’acompte sur prime</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {getAdvanceTypeLabel(advance.advance_type, advance.prime_label)} — acompte versé :{' '}
            <strong>{formatCurrency(acompteVerse)}</strong>
          </p>

          <div>
            <Label htmlFor="prime_final_amount">Montant définitif de la prime (€) *</Label>
            <Input
              id="prime_final_amount"
              type="number"
              step="0.01"
              min="0"
              value={primeFinalAmount}
              onChange={(e) => setPrimeFinalAmount(e.target.value)}
              placeholder="6500.00"
            />
          </div>

          {solde != null && (
            <div className="rounded-md border bg-muted/40 p-3 text-sm">
              <p>
                Prime totale : <strong>{formatCurrency(Number(primeFinalAmount))}</strong>
              </p>
              <p>
                Acompte déjà versé : <strong>- {formatCurrency(acompteVerse)}</strong>
              </p>
              <p className="mt-1 font-semibold">
                Solde à payer (via la prime du bulletin) : {formatCurrency(solde)}
              </p>
              <p className="mt-2 text-muted-foreground">
                L’acompte ({formatCurrency(acompteVerse)}) sera déduit du net sur le bulletin du
                mois sélectionné.
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="reconcile_year">Année bulletin</Label>
              <Input
                id="reconcile_year"
                type="number"
                value={year}
                onChange={(e) => setYear(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="reconcile_month">Mois bulletin</Label>
              <Input
                id="reconcile_month"
                type="number"
                min="1"
                max="12"
                value={month}
                onChange={(e) => setMonth(e.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Réconcilier
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
