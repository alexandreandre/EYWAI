import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Edit, Eye, Loader2, Trash2 } from "lucide-react";

import { deletePromotion, getPromotion, markPromotionEffective } from "@/api/promotions";
import type { Promotion, PromotionListItem } from "@/api/promotions";
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
import { useToast } from "@/components/ui/use-toast";

type PromotionsActionsProps = {
  item: PromotionListItem;
  onView: () => void;
  onEdit: (promotion: Promotion) => void;
};

export function PromotionsActions({ item, onView, onEdit }: PromotionsActionsProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const markEffectiveMutation = useMutation({
    mutationFn: markPromotionEffective,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["promotions"] });
      void queryClient.invalidateQueries({ queryKey: ["promotion-stats"] });
      void queryClient.invalidateQueries({ queryKey: ["documents", "avenant_salaire"] });
      toast({
        title: "Promotion effective",
        description:
          "La promotion a été marquée comme effective et les changements ont été appliqués.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de marquer la promotion comme effective.",
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deletePromotion,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["promotions"] });
      void queryClient.invalidateQueries({ queryKey: ["promotion-stats"] });
      toast({
        title: "Promotion supprimée",
        description: "La promotion a été supprimée avec succès.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de supprimer la promotion.",
        variant: "destructive",
      });
    },
  });

  return (
    <div className="flex items-center justify-end gap-2">
      <Button
        variant="ghost"
        size="sm"
        onClick={onView}
        className="h-8 w-8 p-0"
        title="Voir les détails"
      >
        <Eye className="h-4 w-4" />
      </Button>
      {item.status === "draft" && (
        <>
          <Button
            variant="ghost"
            size="sm"
            onClick={async () => {
              try {
                const res = await getPromotion(item.id);
                onEdit(res.data);
              } catch {
                toast({
                  title: "Erreur",
                  description: "Impossible de charger la promotion.",
                  variant: "destructive",
                });
              }
            }}
            className="h-8 w-8 p-0"
            title="Modifier"
          >
            <Edit className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => markEffectiveMutation.mutate(item.id)}
            className="h-8 w-8 p-0 text-green-600"
            title="Marquer comme effective"
            disabled={markEffectiveMutation.isPending}
          >
            <CheckCircle2 className="h-4 w-4" />
          </Button>
        </>
      )}
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 text-destructive hover:text-destructive"
            title="Supprimer"
            aria-label="Supprimer la promotion"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer la promotion</AlertDialogTitle>
            <AlertDialogDescription>
              Le dossier de promotion de {item.first_name} {item.last_name} sera retiré du
              registre. Cette action est irréversible et ne modifie pas la fiche salarié.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMutation.mutate(item.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? (
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
