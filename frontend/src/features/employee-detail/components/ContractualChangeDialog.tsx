import { Loader2 } from "lucide-react";
import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/api/apiClient";
import { generateDocument } from "@/api/documents";
import { DOCUMENT_TYPE_LABELS, getTemplates, type DocumentTemplate } from "@/api/documentLibrary";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/use-toast";
import type { Employee } from "@/features/employee-detail/types";
import type { ContractualFieldDiff } from "@/utils/employeeContractualWatch";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employeeId: string;
  employee: Employee | null;
  diffs: ContractualFieldDiff[];
  avenantType: string;
  onAvenantTypeChange: (v: string) => void;
  template: string;
  onTemplateChange: (v: string) => void;
  dateEffet: string;
  onDateEffetChange: (v: string) => void;
  motifExtra: string;
  onMotifExtraChange: (v: string) => void;
  onIgnore: () => void;
  onSuccess: (employee: Employee) => void;
}

export function ContractualChangeDialog({
  open,
  onOpenChange,
  employeeId,
  employee,
  diffs,
  avenantType,
  onAvenantTypeChange,
  template,
  onTemplateChange,
  dateEffet,
  onDateEffetChange,
  motifExtra,
  onMotifExtraChange,
  onIgnore,
  onSuccess,
}: Props) {
  const queryClient = useQueryClient();

  const { data: contractualLibTemplates = [] } = useQuery({
    queryKey: ["document-library", "templates", "active", avenantType, open],
    queryFn: () => getTemplates("active"),
    enabled: open && !!avenantType,
  });

  const contractualTemplatesForType = useMemo(
    () =>
      contractualLibTemplates.filter(
        (t: DocumentTemplate) => t.document_type === avenantType && t.status === "active",
      ),
    [contractualLibTemplates, avenantType],
  );

  const contractualGenMut = useMutation({
    mutationFn: generateDocument,
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ["employee-generated-documents", employeeId] });
      onOpenChange(false);
      try {
        const r = await apiClient.get<Employee>(`/api/employees/${employeeId}`);
        onSuccess(r.data);
      } catch {
        if (employee) onSuccess(employee);
      }
      toast({ title: "Avenant généré", description: "Le document a été ajouté à la liste." });
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === "object" && "response" in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Échec",
        description: typeof msg === "string" ? msg : "Génération impossible.",
        variant: "destructive",
      });
    },
  });

  return (
      <Dialog
        open={open}
        onOpenChange={(open) => {
          if (!open) {
            onOpenChange(false);
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Modification contractuelle détectée</DialogTitle>
            <DialogDescription>
              Des champs pouvant nécessiter un avenant ont changé depuis le chargement de la fiche.
              La fiche est déjà enregistrée : vous pouvez générer un avenant ou ignorer cette proposition.
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[40vh] space-y-2 overflow-y-auto rounded-md border bg-muted/40 p-3 text-sm">
            {diffs.map((d) => (
              <p key={d.key}>
                <span className="font-medium">{d.label}</span> : {d.before} → {d.after}
              </p>
            ))}
          </div>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>Type d&apos;avenant</Label>
              <Select value={avenantType} onValueChange={onAvenantTypeChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(
                    [
                      "avenant_salaire",
                      "avenant_poste",
                      "avenant_temps",
                      "avenant_lieu",
                      "avenant_general",
                    ] as const
                  ).map((t) => (
                    <SelectItem key={t} value={t}>
                      {DOCUMENT_TYPE_LABELS[t] ?? t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Modèle</Label>
              <Select value={template} onValueChange={onTemplateChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__eywai__">Standard EYWAI</SelectItem>
                  {contractualTemplatesForType.map((tpl: DocumentTemplate) => (
                    <SelectItem key={tpl.id} value={tpl.id}>
                      {tpl.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Date d&apos;effet</Label>
              <Input
                type="date"
                value={dateEffet}
                onChange={(e) => onDateEffetChange(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label>Motif (optionnel)</Label>
              <Input
                value={motifExtra}
                onChange={(e) => onMotifExtraChange(e.target.value)}
                placeholder="Précisions pour l'avenant"
              />
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => {
                onOpenChange(false);
                onIgnore();
              }}
            >
              Ignorer
            </Button>
            <Button
              disabled={!dateEffet || contractualGenMut.isPending}
              onClick={() => {
                if (!employeeId) return;
                const lines = diffs.map((d) => `${d.label} : ${d.before} → ${d.after}`);
                const auto = `Modification détectée sur la fiche :\n${lines.join("\n")}`;
                const motif = [auto, motifExtra.trim()].filter(Boolean).join("\n\n");
                contractualGenMut.mutate({
                  employee_id: employeeId,
                  document_type: avenantType,
                  category: "avenant",
                  date_effet: dateEffet,
                  motif,
                  template_id: template === "__eywai__" ? null : template,
                });
              }}
            >
              {contractualGenMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Générer l&apos;avenant
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

  );
}
