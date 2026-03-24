// frontend/src/components/saisies-avances/AdvancePaymentModal.tsx

import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, Upload, FileText, X } from "lucide-react";
import { createAdvancePayment, getPaymentUploadUrl, uploadPaymentFile } from '@/api/saisiesAvances';
import type { SalaryAdvance, SalaryAdvancePaymentCreate } from '@/api/saisiesAvances';

interface AdvancePaymentModalProps {
  advance: SalaryAdvance;
  onClose: () => void;
  onSuccess: () => void;
}

export function AdvancePaymentModal({ advance, onClose, onSuccess }: AdvancePaymentModalProps) {
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [formData, setFormData] = useState<Partial<SalaryAdvancePaymentCreate>>({
    advance_id: advance.id,
    payment_date: new Date().toISOString().split('T')[0],
    payment_method: 'virement',
  });

  const approvedAmount = Number(advance.approved_amount || 0);
  const remainingAmount = Number(advance.remaining_amount || 0);
  // Le montant restant à verser = montant approuvé - montant déjà versé
  // Pour simplifier, on utilise approved_amount comme maximum (le backend validera)
  const maxPaymentAmount = approvedAmount;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      // Vérifier le type de fichier (PDF ou image)
      const validTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
      if (!validTypes.includes(file.type)) {
        toast({
          title: "Erreur",
          description: "Veuillez sélectionner un fichier PDF ou une image (JPG, PNG, WebP).",
          variant: "destructive",
        });
        return;
      }
      // Vérifier la taille (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        toast({
          title: "Erreur",
          description: "Le fichier est trop volumineux (max 10MB).",
          variant: "destructive",
        });
        return;
      }
      setProofFile(file);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.payment_amount || !formData.payment_date) {
      toast({
        title: "Erreur",
        description: "Veuillez remplir tous les champs obligatoires.",
        variant: "destructive",
      });
      return;
    }

    const paymentAmount = Number(formData.payment_amount);
    if (paymentAmount <= 0) {
      toast({
        title: "Erreur",
        description: "Le montant doit être supérieur à 0.",
        variant: "destructive",
      });
      return;
    }

    if (paymentAmount > maxPaymentAmount) {
      toast({
        title: "Erreur",
        description: `Le montant ne peut pas dépasser ${maxPaymentAmount.toFixed(2)}€ (reste à payer).`,
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);
    setIsUploading(false);

    try {
      let proofFilePath: string | undefined;
      let proofFileName: string | undefined;
      let proofFileType: string | undefined;

      // Upload de la preuve si fournie
      if (proofFile) {
        setIsUploading(true);
        try {
          const { path, signedURL } = await getPaymentUploadUrl(proofFile.name);
          await uploadPaymentFile(signedURL, proofFile);
          proofFilePath = path;
          proofFileName = proofFile.name;
          proofFileType = proofFile.type;
        } catch (uploadError: any) {
          toast({
            title: "Erreur",
            description: `Erreur lors de l'upload de la preuve: ${uploadError.message}`,
            variant: "destructive",
          });
          setIsLoading(false);
          setIsUploading(false);
          return;
        }
        setIsUploading(false);
      }

      // Créer le paiement
      const paymentData: SalaryAdvancePaymentCreate = {
        advance_id: advance.id,
        payment_amount: paymentAmount,
        payment_date: formData.payment_date!,
        payment_method: formData.payment_method as 'virement' | 'cheque' | 'especes',
        proof_file_path: proofFilePath,
        proof_file_name: proofFileName,
        proof_file_type: proofFileType,
        notes: formData.notes,
      };

      await createAdvancePayment(paymentData);
      
      toast({
        title: "Succès",
        description: "Paiement enregistré avec succès.",
      });
      
      // Délai pour s'assurer que la base de données est synchronisée
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Appeler onSuccess pour rafraîchir la liste
      onSuccess();
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.response?.data?.detail || "Impossible d'enregistrer le paiement.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
      setIsUploading(false);
    }
  };

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Enregistrer un paiement</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="p-3 bg-blue-50 rounded-md">
            <p className="text-sm text-blue-900">
              <strong>Montant approuvé :</strong> {approvedAmount.toFixed(2)}€
              {remainingAmount > 0 && (
                <> | <strong>Reste à payer :</strong> {remainingAmount.toFixed(2)}€</>
              )}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Montant du paiement (€) *</Label>
              <Input
                type="number"
                step="0.01"
                min="0.01"
                max={maxPaymentAmount}
                value={formData.payment_amount || ''}
                onChange={(e) => setFormData({ ...formData, payment_amount: parseFloat(e.target.value) })}
                placeholder="0.00"
                required
              />
              <p className="text-xs text-muted-foreground mt-1">
                Maximum : {maxPaymentAmount.toFixed(2)}€
              </p>
            </div>

            <div>
              <Label>Date de paiement *</Label>
              <Input
                type="date"
                value={formData.payment_date || ''}
                onChange={(e) => setFormData({ ...formData, payment_date: e.target.value })}
                required
              />
            </div>
          </div>

          <div>
            <Label>Mode de paiement</Label>
            <Select
              value={formData.payment_method || 'virement'}
              onValueChange={(value: any) => setFormData({ ...formData, payment_method: value })}
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

          <div>
            <Label>Preuve de paiement (PDF ou image) *</Label>
            <div className="mt-2">
              <Input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.webp"
                onChange={handleFileChange}
                className="cursor-pointer"
                required
              />
              <p className="text-xs text-muted-foreground mt-1">
                Formats acceptés : PDF, JPG, PNG, WebP (max 10MB)
              </p>
              {proofFile && (
                <div className="mt-2 flex items-center gap-2 p-2 bg-muted rounded-md">
                  <FileText className="h-4 w-4" />
                  <span className="text-sm flex-1">{proofFile.name}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setProofFile(null)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
          </div>

          <div>
            <Label>Notes (optionnel)</Label>
            <Textarea
              value={formData.notes || ''}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              placeholder="Notes sur ce paiement..."
              rows={3}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
              Annuler
            </Button>
            <Button type="submit" disabled={isLoading || isUploading}>
              {(isLoading || isUploading) && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {isUploading ? 'Upload en cours...' : 'Enregistrer le paiement'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
