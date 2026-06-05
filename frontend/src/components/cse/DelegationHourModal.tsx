// frontend/src/components/cse/DelegationHourModal.tsx
// Modal pour saisir une heure de délégation

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import {
  createDelegationHour,
  type DelegationHourCreate,
  type DelegationHourSource,
} from "@/api/cse";
import { Loader2 } from "lucide-react";

interface DelegationHourModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employeeId?: string;
}

export function DelegationHourModal({
  open,
  onOpenChange,
  employeeId: propEmployeeId,
}: DelegationHourModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [durationHours, setDurationHours] = useState("");
  const [reason, setReason] = useState("");
  const [source, setSource] = useState<DelegationHourSource>("propre");
  const [originMonth, setOriginMonth] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: DelegationHourCreate) => createDelegationHour(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "delegation"] });
      queryClient.invalidateQueries({ queryKey: ["cse", "my-delegation-quota"] });
      queryClient.invalidateQueries({ queryKey: ["cse", "my-delegation-hours"] });
      toast({
        title: "Heure saisie",
        description: "L'heure de délégation a été enregistrée avec succès.",
      });
      onOpenChange(false);
      setDate(new Date().toISOString().split('T')[0]);
      setDurationHours("");
      setReason("");
    },
    onError: (error: any) => {
      toast({
        title: "Erreur",
        description: error.message || "Erreur lors de la saisie",
        variant: "destructive",
      });
    },
  });

  const handleSubmit = () => {
    if (!date || !durationHours || !reason) {
      toast({
        title: "Champs requis",
        description: "La date, la durée et le motif sont obligatoires",
        variant: "destructive",
      });
      return;
    }

    const hours = parseFloat(durationHours);
    if (isNaN(hours) || hours <= 0) {
      toast({
        title: "Erreur",
        description: "La durée doit être un nombre positif",
        variant: "destructive",
      });
      return;
    }

    createMutation.mutate({
      employee_id: propEmployeeId || undefined,
      date,
      duration_hours: hours,
      reason,
      source,
      origin_month: source === "reportee" && originMonth ? originMonth : undefined,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Saisir une heure de délégation</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="date">Date *</Label>
            <Input
              id="date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="duration">Durée (heures) *</Label>
            <Input
              id="duration"
              type="number"
              step="0.5"
              min="0.5"
              value={durationHours}
              onChange={(e) => setDurationHours(e.target.value)}
              placeholder="Ex: 2.5"
            />
          </div>
          <div>
            <Label htmlFor="source">Source</Label>
            <Select value={source} onValueChange={(v) => setSource(v as DelegationHourSource)}>
              <SelectTrigger id="source">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="propre">Heures du mois</SelectItem>
                <SelectItem value="reportee">Heures reportées</SelectItem>
                <SelectItem value="mutualisee">Heures mutualisées reçues</SelectItem>
                <SelectItem value="exceptionnelle">Circonstances exceptionnelles</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {source === "reportee" && (
            <div>
              <Label htmlFor="origin-month">Mois d&apos;origine (report)</Label>
              <Input
                id="origin-month"
                type="month"
                value={originMonth ? originMonth.slice(0, 7) : ""}
                onChange={(e) => setOriginMonth(`${e.target.value}-01`)}
              />
            </div>
          )}
          <div>
            <Label htmlFor="reason">Motif *</Label>
            <Textarea
              id="reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Ex: Réunion CSE mensuelle"
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button onClick={handleSubmit} disabled={createMutation.isPending}>
            {createMutation.isPending && (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            )}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
