// frontend/src/components/saisies-avances/SalaryAdvanceApprovalModal.tsx

import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { Loader2 } from "lucide-react";
import { approveSalaryAdvance } from '@/api/saisiesAvances';
import type { SalaryAdvance, SalaryAdvanceApprove } from '@/api/saisiesAvances';

interface SalaryAdvanceApprovalModalProps {
  advance: SalaryAdvance;
  onClose: () => void;
  onSuccess: () => void;
}

export function SalaryAdvanceApprovalModal({ advance, onClose, onSuccess }: SalaryAdvanceApprovalModalProps) {
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [approvalData, setApprovalData] = useState<SalaryAdvanceApprove>({
    approved_amount: advance.requested_amount,
    payment_method: 'virement',
    repayment_mode: 'single', // Valeur par défaut, non affichée dans l'interface
    repayment_months: 1, // Valeur par défaut, non affichée dans l'interface
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await approveSalaryAdvance(advance.id, approvalData);
      toast({
        title: "Succès",
        description: "Avance approuvée avec succès.",
      });
      onSuccess();
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Impossible d'approuver l'avance.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Approuver l'avance</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label>Montant demandé</Label>
            <p className="text-lg font-semibold">{Number(advance.requested_amount || 0).toFixed(2)}€</p>
          </div>

          <div>
            <Label>Montant approuvé (€)</Label>
            <Input
              type="number"
              step="0.01"
              value={approvalData.approved_amount || advance.requested_amount}
              onChange={(e) => setApprovalData({ ...approvalData, approved_amount: parseFloat(e.target.value) })}
              max={advance.requested_amount}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Peut être inférieur au montant demandé
            </p>
          </div>

          <div>
            <Label>Mode de paiement</Label>
            <Select
              value={approvalData.payment_method || 'virement'}
              onValueChange={(value: any) => setApprovalData({ ...approvalData, payment_method: value })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="virement">Virement</SelectItem>
                <SelectItem value="cheque">Chèque</SelectItem>
                <SelectItem value="especes">Espèces</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Approuver
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
