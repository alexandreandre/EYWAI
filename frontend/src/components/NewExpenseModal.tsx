// Fichier : src/components/NewExpenseModal.tsx

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/components/ui/use-toast";
import { Loader2 } from "lucide-react";
import * as expensesApi from "@/api/expenses";
import axios from "axios"; // Import axios to check for its error structure

interface NewExpenseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const expenseTypes: expensesApi.ExpenseType[] = ["Restaurant", "Transport", "Hôtel", "Fournitures", "Autre"];

export function NewExpenseModal({ isOpen, onClose, onSuccess }: NewExpenseModalProps) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [date, setDate] = useState("");
  const [amount, setAmount] = useState("");
  const [type, setType] = useState<expensesApi.ExpenseType | "">("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const resetForm = () => {
    setDate(""); setAmount(""); setType(""); setDescription(""); setFile(null); setError("");
  };

  useEffect(() => { if (isOpen) resetForm(); }, [isOpen]);

  const handleSubmit = async () => {
    if (!user || !date || !amount || !type || !file) {
      setError("Tous les champs (sauf description) et un justificatif sont requis.");
      return;
    }
    setIsLoading(true);
    setError("");

    try {
      // 1. Obtenir l'URL d'upload EN PASSANT LE NOM DU FICHIER
      const { path, signedURL } = await expensesApi.getUploadUrl(file.name); // <-- Passer file.name

      // 2. Uploader le fichier (inchangé)
      await expensesApi.uploadFile(signedURL, file);

      // 3. Créer la note de frais en BDD EN PASSANT LE NOM DU FICHIER
      await expensesApi.createExpense({
        employee_id: user.id,
        date,
        amount: parseFloat(amount),
        type,
        description,
        receipt_url: path,
        filename: file.name, // <-- Passer file.name ici aussi
      });

      toast({ title: "Succès", description: "Note de frais soumise." });
      onSuccess();
      onClose();
    } catch (err) {
      // ... (gestion d'erreur inchangée) ...
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouvelle dépense</DialogTitle></DialogHeader>
        <div className="space-y-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2"><Label htmlFor="date">Date</Label><Input id="date" type="date" value={date} onChange={e => setDate(e.target.value)} /></div>
            <div className="grid gap-2"><Label htmlFor="amount">Montant (€)</Label><Input id="amount" type="number" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} /></div>
          </div>
          <div className="grid gap-2"><Label htmlFor="type">Type</Label>
            <Select value={type} onValueChange={(v) => setType(v as any)}>
              <SelectTrigger><SelectValue placeholder="Sélectionner un type..." /></SelectTrigger>
              <SelectContent>{expenseTypes.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-2"><Label htmlFor="receipt">Justificatif</Label><Input id="receipt" type="file" onChange={e => setFile(e.target.files ? e.target.files[0] : null)} /></div>
          <div className="grid gap-2"><Label htmlFor="description">Description (facultatif)</Label><Textarea id="description" placeholder="Ex: Dîner client M. Dupont" value={description} onChange={e => setDescription(e.target.value)} /></div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Annuler</Button>
          <Button onClick={handleSubmit} disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Soumettre
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}