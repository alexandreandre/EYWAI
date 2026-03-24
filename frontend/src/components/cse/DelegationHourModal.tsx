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
import { useToast } from "@/components/ui/use-toast";
import { createDelegationHour, type DelegationHourCreate } from "@/api/cse";
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

  const createMutation = useMutation({
    mutationFn: (data: DelegationHourCreate) => createDelegationHour(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "delegation"] });
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
