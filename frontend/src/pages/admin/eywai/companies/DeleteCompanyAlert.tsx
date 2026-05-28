import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { Loader2, ChevronDown } from "lucide-react";
import type { AdminCompany } from "@/pages/admin/eywai/companies/types";

type DeleteCompanyAlertProps = {
  company: AdminCompany | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  deleting: boolean;
  onConfirm: () => void;
};

export function DeleteCompanyAlert({
  company,
  open,
  onOpenChange,
  deleting,
  onConfirm,
}: DeleteCompanyAlertProps) {
  if (!company) return null;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-lg">
        <AlertDialogHeader>
          <AlertDialogTitle>Suppression définitive</AlertDialogTitle>
          <AlertDialogDescription>
            Cette action est irréversible. L&apos;entreprise{" "}
            <strong>{company.company_name}</strong> et toutes ses données associées seront
            supprimées.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="rounded-lg bg-muted p-4 text-sm">
          <p className="font-medium">{company.company_name}</p>
          {company.email ? (
            <p className="text-muted-foreground">{company.email}</p>
          ) : null}
          <p className="mt-2 text-muted-foreground">
            {company.employees_count ?? 0} employé(s) · {company.users_count ?? 0}{" "}
            utilisateur(s)
          </p>
        </div>

        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="w-full justify-between px-0">
              Voir le détail des données supprimées
              <ChevronDown className="h-4 w-4" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-muted-foreground">
              <li>Tous les employés et bulletins de paie</li>
              <li>Contrats, absences, notes de frais</li>
              <li>Plannings et saisies mensuelles</li>
              <li>Accès utilisateurs et conventions collectives</li>
              <li>Configurations de paie</li>
            </ul>
          </CollapsibleContent>
        </Collapsible>

        <AlertDialogFooter>
          <AlertDialogCancel disabled={deleting}>Annuler</AlertDialogCancel>
          <AlertDialogAction
            disabled={deleting}
            onClick={(e) => {
              e.preventDefault();
              onConfirm();
            }}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {deleting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Suppression…
              </>
            ) : (
              "Supprimer définitivement"
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
