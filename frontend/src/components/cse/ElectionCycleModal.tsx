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
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/components/ui/use-toast";
import { createElectionCycle, type ElectionCycleCreate } from "@/api/cse";
import { Loader2 } from "lucide-react";

interface ElectionCycleModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ElectionCycleModal({ open, onOpenChange }: ElectionCycleModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [cycleName, setCycleName] = useState("");
  const [mandateEndDate, setMandateEndDate] = useState("");
  const [electionDate, setElectionDate] = useState("");
  const [isCarence, setIsCarence] = useState(false);

  const createMutation = useMutation({
    mutationFn: (data: ElectionCycleCreate) => createElectionCycle(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "election-cycles"] });
      queryClient.invalidateQueries({ queryKey: ["cse", "election-alerts"] });
      toast({
        title: "Cycle créé",
        description: "Le cycle électoral a été enregistré.",
      });
      setCycleName("");
      setMandateEndDate("");
      setElectionDate("");
      setIsCarence(false);
      onOpenChange(false);
    },
    onError: (error: unknown) => {
      const msg =
        error && typeof error === "object" && "message" in error
          ? String((error as { message?: string }).message)
          : "Erreur lors de la création";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    },
  });

  const handleSubmit = () => {
    if (!cycleName.trim() || !mandateEndDate) {
      toast({
        title: "Champs requis",
        description: "Le nom du cycle et la fin de mandat sont obligatoires.",
        variant: "destructive",
      });
      return;
    }
    createMutation.mutate({
      cycle_name: cycleName.trim(),
      mandate_end_date: mandateEndDate,
      election_date: electionDate || null,
      outcome: isCarence ? "carence" : undefined,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Nouveau cycle électoral</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="cycle-name">Nom du cycle *</Label>
            <Input
              id="cycle-name"
              value={cycleName}
              onChange={(e) => setCycleName(e.target.value)}
              placeholder="Ex : Renouvellement 2026"
            />
          </div>
          <div>
            <Label htmlFor="mandate-end">Fin de mandat *</Label>
            <Input
              id="mandate-end"
              type="date"
              value={mandateEndDate}
              onChange={(e) => setMandateEndDate(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="election-date">Date des élections</Label>
            <Input
              id="election-date"
              type="date"
              value={electionDate}
              onChange={(e) => setElectionDate(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2 rounded-lg border p-3">
            <Checkbox
              id="carence-outcome"
              checked={isCarence}
              onCheckedChange={(v) => setIsCarence(Boolean(v))}
            />
            <Label htmlFor="carence-outcome" className="cursor-pointer text-sm font-normal">
              Issue : carence (aucun candidat aux élections)
            </Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button onClick={handleSubmit} disabled={createMutation.isPending}>
            {createMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Créer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
