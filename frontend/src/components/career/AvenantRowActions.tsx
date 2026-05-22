import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  downloadDocument,
  triggerSignedDocumentDownload,
  updateDocumentStatus,
  type DocumentStatus,
  type GeneratedDocument,
} from "@/api/documents";
import { Button } from "@/components/ui/button";
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

  const handleDownload = async () => {
    try {
      const r = await downloadDocument(document.id);
      triggerSignedDocumentDownload(r, document.file_name || "avenant.pdf");
    } catch {
      toast({
        title: "Téléchargement",
        description: "Impossible d'obtenir le lien.",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={!document.file_url}
        onClick={() => void handleDownload()}
      >
        Télécharger
      </Button>
      <Select
        value={document.status}
        onValueChange={(v) =>
          statusMut.mutate({ id: document.id, status: v as DocumentStatus })
        }
        disabled={statusMut.isPending}
      >
        <SelectTrigger className="h-8 w-[130px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="brouillon">Brouillon</SelectItem>
          <SelectItem value="envoye">Envoyé</SelectItem>
          <SelectItem value="signe">Signé</SelectItem>
          <SelectItem value="archive">Archivé</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
