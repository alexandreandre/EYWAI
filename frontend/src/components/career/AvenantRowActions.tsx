import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Loader2, Trash2 } from "lucide-react";
import {
  deleteDocument,
  downloadDocument,
  triggerSignedDocumentDownload,
  updateDocumentStatus,
  type DocumentFileFormat,
  type DocumentStatus,
  type GeneratedDocument,
} from "@/api/documents";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/use-toast";
import { AVENANTS_QUERY_KEY } from "@/lib/careerActivity";

type AvenantRowActionsProps = {
  document: GeneratedDocument;
  companyId: string;
};

export function AvenantRowActions({ document, companyId }: AvenantRowActionsProps) {
  const queryClient = useQueryClient();

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: DocumentStatus }) =>
      updateDocumentStatus(id, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...AVENANTS_QUERY_KEY, companyId] });
      toast({ title: "Statut mis à jour" });
    },
    onError: () => {
      toast({
        title: "Mise à jour impossible",
        description: "Réessayez plus tard.",
        variant: "destructive",
      });
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...AVENANTS_QUERY_KEY, companyId] });
      toast({ title: "Avenant supprimé" });
    },
    onError: () => {
      toast({
        title: "Suppression impossible",
        description: "Réessayez plus tard.",
        variant: "destructive",
      });
    },
  });

  const handleDownload = async (format: DocumentFileFormat = "pdf") => {
    try {
      const r = await downloadDocument(document.id, format);
      const fallback = format === "docx" ? "avenant.docx" : "avenant.pdf";
      triggerSignedDocumentDownload(r, fallback);
    } catch {
      toast({
        title: "Téléchargement",
        description: "Impossible d'obtenir le lien.",
        variant: "destructive",
      });
    }
  };

  const hasWordExport = Boolean(document.docx_file_url);

  return (
    <div className="flex flex-nowrap items-center justify-end gap-1.5">
      {hasWordExport ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={!document.file_url}
              className="h-8 w-8 p-0"
              aria-label="Télécharger l'avenant"
              title="Télécharger"
            >
              <Download className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => void handleDownload("pdf")}>
              <Download className="mr-2 h-4 w-4" />
              PDF
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => void handleDownload("docx")}>
              <FileText className="mr-2 h-4 w-4" />
              Word (.docx) — à retravailler
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ) : (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={!document.file_url}
          onClick={() => void handleDownload("pdf")}
          className="h-8 w-8 p-0"
          aria-label="Télécharger l'avenant"
          title="Télécharger"
        >
          <Download className="h-4 w-4" />
        </Button>
      )}
      <Select
        value={document.status}
        onValueChange={(v) =>
          statusMut.mutate({ id: document.id, status: v as DocumentStatus })
        }
        disabled={statusMut.isPending}
      >
        <SelectTrigger className="h-8 w-[116px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="brouillon">Brouillon</SelectItem>
          <SelectItem value="envoye">Envoyé</SelectItem>
          <SelectItem value="signe">Signé</SelectItem>
          <SelectItem value="archive">Archivé</SelectItem>
        </SelectContent>
      </Select>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 text-destructive hover:text-destructive"
            aria-label="Supprimer l'avenant"
            title="Supprimer"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cet avenant ?</AlertDialogTitle>
            <AlertDialogDescription>
              L&apos;avenant sera retiré du registre. Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMut.mutate(document.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMut.isPending}
            >
              {deleteMut.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Suppression...
                </>
              ) : (
                "Supprimer"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
