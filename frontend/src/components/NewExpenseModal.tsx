import { useState, useEffect, useMemo } from "react";
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
import axios from "axios";
import {
  computeVatBreakdown,
  DEFAULT_VAT_BY_EXPENSE_TYPE,
  formatVatRateLabel,
  parseVatRateInput,
  STANDARD_VAT_RATES,
  type VatRatePreset,
} from "@/lib/expenseVat";

interface NewExpenseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const expenseTypes: expensesApi.ExpenseType[] = ["Restaurant", "Transport", "Hôtel", "Fournitures", "Autre"];

function presetFromRate(rate: number): VatRatePreset {
  if ((STANDARD_VAT_RATES as readonly number[]).includes(rate)) {
    return rate as VatRatePreset;
  }
  return "custom";
}

export function NewExpenseModal({ isOpen, onClose, onSuccess }: NewExpenseModalProps) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [date, setDate] = useState("");
  const [amount, setAmount] = useState("");
  const [type, setType] = useState<expensesApi.ExpenseType | "">("");
  const [vatPreset, setVatPreset] = useState<VatRatePreset>(20);
  const [customVatRate, setCustomVatRate] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const resetForm = () => {
    setDate("");
    setAmount("");
    setType("");
    setVatPreset(20);
    setCustomVatRate("");
    setDescription("");
    setFile(null);
    setError("");
  };

  useEffect(() => {
    if (isOpen) resetForm();
  }, [isOpen]);

  const resolvedVatRate = useMemo(() => {
    if (vatPreset === "custom") {
      return parseVatRateInput(customVatRate);
    }
    return vatPreset;
  }, [vatPreset, customVatRate]);

  const vatPreview = useMemo(() => {
    const ttc = parseFloat(amount.replace(",", "."));
    if (!Number.isFinite(ttc) || ttc <= 0 || resolvedVatRate == null) return null;
    return computeVatBreakdown(ttc, resolvedVatRate);
  }, [amount, resolvedVatRate]);

  const handleTypeChange = (value: expensesApi.ExpenseType) => {
    setType(value);
    const suggested = DEFAULT_VAT_BY_EXPENSE_TYPE[value];
    const preset = presetFromRate(suggested);
    setVatPreset(preset);
    if (preset === "custom") {
      setCustomVatRate(String(suggested));
    } else {
      setCustomVatRate("");
    }
  };

  const handleSubmit = async () => {
    if (!user || !date || !amount || !type || !file) {
      setError("Tous les champs (sauf description) et un justificatif sont requis.");
      return;
    }
    const amountTtc = parseFloat(amount.replace(",", "."));
    if (!Number.isFinite(amountTtc) || amountTtc <= 0) {
      setError("Indiquez un montant TTC valide.");
      return;
    }
    if (resolvedVatRate == null) {
      setError("Indiquez un taux de TVA valide (entre 0 et 100 %).");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const { path, signedURL } = await expensesApi.getUploadUrl(file.name);
      await expensesApi.uploadFile(signedURL, file);

      await expensesApi.createExpense({
        date,
        amount: amountTtc,
        vat_rate: resolvedVatRate,
        type,
        description,
        receipt_url: path,
        filename: file.name,
      });

      toast({ title: "Succès", description: "Note de frais soumise." });
      onSuccess();
      onClose();
    } catch (err) {
      const message =
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : "Impossible d'envoyer la note de frais. Réessayez ou contactez les RH.";
      setError(message);
      toast({ title: "Erreur", description: message, variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvelle dépense</DialogTitle>
          <p className="text-sm text-muted-foreground">
            Le justificatif (photo ou PDF) est obligatoire. Le montant saisi est le montant TTC.
          </p>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="date">Date</Label>
              <Input id="date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="amount">Montant TTC (€)</Label>
              <Input
                id="amount"
                type="number"
                min="0"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="type">Type</Label>
            <Select value={type} onValueChange={(v) => handleTypeChange(v as expensesApi.ExpenseType)}>
              <SelectTrigger id="type">
                <SelectValue placeholder="Sélectionner un type..." />
              </SelectTrigger>
              <SelectContent>
                {expenseTypes.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="vat-rate">Taux de TVA applicable</Label>
            <Select
              value={String(vatPreset)}
              onValueChange={(v) => {
                if (v === "custom") {
                  setVatPreset("custom");
                  return;
                }
                setVatPreset(Number(v) as VatRatePreset);
                setCustomVatRate("");
              }}
            >
              <SelectTrigger id="vat-rate">
                <SelectValue placeholder="Choisir un taux..." />
              </SelectTrigger>
              <SelectContent>
                {STANDARD_VAT_RATES.map((rate) => (
                  <SelectItem key={rate} value={String(rate)}>
                    {formatVatRateLabel(rate)}
                  </SelectItem>
                ))}
                <SelectItem value="custom">Taux personnalisé</SelectItem>
              </SelectContent>
            </Select>
            {vatPreset === "custom" && (
              <Input
                type="number"
                min="0"
                max="100"
                step="0.01"
                placeholder="Ex. 8.5"
                value={customVatRate}
                onChange={(e) => setCustomVatRate(e.target.value)}
              />
            )}
            {vatPreview && (
              <p className="rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground tabular-nums">
                HT {vatPreview.amountHt.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
                {" · "}
                TVA {resolvedVatRate != null ? formatVatRateLabel(resolvedVatRate) : "—"}
                {" · "}
                {vatPreview.vatAmount.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
              </p>
            )}
          </div>

          <div className="grid gap-2">
            <Label htmlFor="receipt">Justificatif</Label>
            <Input
              id="receipt"
              type="file"
              accept="image/*,application/pdf,.heic,.heif"
              capture="environment"
              onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)}
            />
            <p className="text-xs text-muted-foreground">PDF ou image (photo sur mobile)</p>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="description">Description (facultatif)</Label>
            <Textarea
              id="description"
              placeholder="Ex: Dîner client M. Dupont"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Annuler
          </Button>
          <Button onClick={handleSubmit} disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Soumettre
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
