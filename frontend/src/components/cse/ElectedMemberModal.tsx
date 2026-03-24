// frontend/src/components/cse/ElectedMemberModal.tsx
// Modal pour créer/éditer un élu CSE

import { useState, useEffect } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { useToast } from "@/components/ui/use-toast";
import {
  createElectedMember,
  updateElectedMember,
  type ElectedMemberCreate,
  type ElectedMemberUpdate,
  type ElectedMemberListItem,
} from "@/api/cse";
import { Loader2, Check, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import apiClient from "@/api/apiClient";

interface ElectedMemberModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  member?: ElectedMemberListItem;
}

export function ElectedMemberModal({
  open,
  onOpenChange,
  member,
}: ElectedMemberModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [employeeId, setEmployeeId] = useState("");
  const [role, setRole] = useState<"titulaire" | "suppleant" | "secretaire" | "tresorier" | "autre">("titulaire");
  const [college, setCollege] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [notes, setNotes] = useState("");
  const [employees, setEmployees] = useState<Array<{ id: string; first_name: string; last_name: string }>>([]);
  const [employeePopoverOpen, setEmployeePopoverOpen] = useState(false);

  useEffect(() => {
    if (member) {
      setEmployeeId(member.employee_id);
      setRole(member.role);
      setCollege(member.college || "");
      setStartDate(member.start_date.split('T')[0]);
      setEndDate(member.end_date.split('T')[0]);
    } else {
      setEmployeeId("");
      setRole("titulaire");
      setCollege("");
      setStartDate("");
      setEndDate("");
      setNotes("");
    }
  }, [member, open]);

  // Charger la liste des employés
  useEffect(() => {
    if (open) {
      apiClient
        .get("/api/employees", { params: { limit: 100 } })
        .then((res) => {
          setEmployees(res.data || []);
        })
        .catch(() => {
          // Erreur silencieuse
        });
    }
  }, [open]);

  const createMutation = useMutation({
    mutationFn: (data: ElectedMemberCreate) => createElectedMember(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "elected-members"] });
      toast({
        title: "Élu créé",
        description: "Le mandat a été créé avec succès.",
      });
      onOpenChange(false);
    },
    onError: (error: any) => {
      toast({
        title: "Erreur",
        description: error.message || "Erreur lors de la création",
        variant: "destructive",
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ memberId, data }: { memberId: string; data: ElectedMemberUpdate }) =>
      updateElectedMember(memberId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "elected-members"] });
      toast({
        title: "Mandat mis à jour",
        description: "Le mandat a été modifié avec succès.",
      });
      onOpenChange(false);
    },
    onError: (error: any) => {
      toast({
        title: "Erreur",
        description: error.message || "Erreur lors de la mise à jour",
        variant: "destructive",
      });
    },
  });

  const handleSubmit = () => {
    if (!employeeId || !startDate || !endDate) {
      toast({
        title: "Champs requis",
        description: "L'employé, la date de début et la date de fin sont obligatoires",
        variant: "destructive",
      });
      return;
    }

    if (new Date(endDate) < new Date(startDate)) {
      toast({
        title: "Erreur de dates",
        description: "La date de fin doit être après la date de début",
        variant: "destructive",
      });
      return;
    }

    if (member) {
      updateMutation.mutate({
        memberId: member.id,
        data: {
          role,
          college: college || null,
          start_date: startDate,
          end_date: endDate,
          notes: notes || null,
        },
      });
    } else {
      createMutation.mutate({
        employee_id: employeeId,
        role,
        college: college || null,
        start_date: startDate,
        end_date: endDate,
        notes: notes || null,
      });
    }
  };

  const selectedEmployee = employees.find((e) => e.id === employeeId);
  const displayEmployee = selectedEmployee
    ? `${selectedEmployee.first_name} ${selectedEmployee.last_name}`
    : "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {member ? "Modifier le mandat" : "Ajouter un élu CSE"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {!member && (
            <div>
              <Label>Employé *</Label>
              <Popover open={employeePopoverOpen} onOpenChange={setEmployeePopoverOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={employeePopoverOpen}
                    className="w-full justify-between font-normal"
                  >
                    {displayEmployee || "Rechercher et sélectionner un employé..."}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                  <Command>
                    <CommandInput placeholder="Rechercher un employé..." />
                    <CommandList>
                      <CommandEmpty>Aucun employé trouvé.</CommandEmpty>
                      <CommandGroup>
                        {employees.map((emp) => (
                          <CommandItem
                            key={emp.id}
                            value={`${emp.first_name} ${emp.last_name}`}
                            onSelect={() => {
                              setEmployeeId(emp.id);
                              setEmployeePopoverOpen(false);
                            }}
                          >
                            <Check
                              className={cn(
                                "mr-2 h-4 w-4",
                                employeeId === emp.id ? "opacity-100" : "opacity-0"
                              )}
                            />
                            {emp.first_name} {emp.last_name}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>
          )}
          <div>
            <Label htmlFor="role">Rôle CSE *</Label>
            <Select value={role} onValueChange={(v: any) => setRole(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="titulaire">Titulaire</SelectItem>
                <SelectItem value="suppleant">Suppléant</SelectItem>
                <SelectItem value="secretaire">Secrétaire</SelectItem>
                <SelectItem value="tresorier">Trésorier</SelectItem>
                <SelectItem value="autre">Autre</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="college">Collège</Label>
            <Input
              id="college"
              value={college}
              onChange={(e) => setCollege(e.target.value)}
              placeholder="Ex: Cadres, Non-cadres"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="startDate">Date de début *</Label>
              <Input
                id="startDate"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="endDate">Date de fin *</Label>
              <Input
                id="endDate"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>
          <div>
            <Label htmlFor="notes">Notes</Label>
            <Textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Notes additionnelles sur le mandat"
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={createMutation.isPending || updateMutation.isPending}
          >
            {(createMutation.isPending || updateMutation.isPending) && (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            )}
            {member ? "Modifier" : "Créer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
