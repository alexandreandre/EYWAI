import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileText, Loader2, Trash2, Upload } from "lucide-react";
import {
  deposerPieceSociete,
  fetchPiecesSociete,
  lienPieceSociete,
  retirerPieceSociete,
  type FichierPiece,
  type PieceSociete,
} from "@/api/company";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { resumePieces } from "@/features/company/lib/piecesSociete";
import { useToast } from "@/hooks/use-toast";

const CLE = ["company", "pieces"];

/** Le message de l'API (format refusé, fichier trop gros…), sinon un message général. */
function messageDErreur(erreur: unknown): string {
  const detail = (erreur as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : "Réessayez dans un instant.";
}

function LignePiece({
  piece,
  canEdit,
  envoi,
  onDeposer,
  onOuvrir,
  onRetirer,
}: {
  piece: PieceSociete;
  canEdit: boolean;
  envoi: boolean;
  onDeposer: (fichier: File) => void;
  onOuvrir: (fichier: FichierPiece) => void;
  onRetirer: (fichier: FichierPiece) => void;
}) {
  const champ = useRef<HTMLInputElement>(null);
  const deposee = piece.fichiers.length > 0;
  return (
    <li className="flex flex-col gap-2 py-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium">{piece.libelle}</span>
          {deposee ? (
            <Badge variant="secondary" className="gap-1">
              <CheckCircle2 className="h-3 w-3" />
              Déposée
            </Badge>
          ) : piece.attendue ? (
            <Badge variant="outline" className="border-amber-300 text-amber-800">
              À déposer
            </Badge>
          ) : null}
        </div>
        <p className="text-xs text-muted-foreground">{piece.pourquoi}</p>
        {piece.fichiers.map((fichier) => (
          <div key={fichier.chemin} className="flex items-center gap-1">
            <Button
              type="button"
              variant="link"
              size="sm"
              className="h-auto min-w-0 p-0 text-xs"
              onClick={() => onOuvrir(fichier)}
            >
              <FileText className="mr-1 h-3 w-3 shrink-0" />
              <span className="truncate">{fichier.nom}</span>
            </Button>
            {canEdit ? (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                aria-label={`Retirer ${fichier.nom}`}
                onClick={() => onRetirer(fichier)}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            ) : null}
          </div>
        ))}
      </div>
      {canEdit ? (
        <>
          <input
            ref={champ}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            className="hidden"
            aria-label={`Fichier pour ${piece.libelle}`}
            onChange={(e) => {
              const fichier = e.target.files?.[0];
              if (fichier) onDeposer(fichier);
              e.target.value = "";
            }}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="shrink-0"
            disabled={envoi}
            onClick={() => champ.current?.click()}
          >
            {envoi ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Upload className="mr-1.5 h-3.5 w-3.5" />
            )}
            Déposer
          </Button>
        </>
      ) : null}
    </li>
  );
}

export function CompanyPiecesCard({ canEdit }: { canEdit: boolean }) {
  const { toast } = useToast();
  const client = useQueryClient();
  const [aRetirer, setARetirer] = useState<FichierPiece | null>(null);
  const { data, isLoading, isError } = useQuery({ queryKey: CLE, queryFn: fetchPiecesSociete });

  const depot = useMutation({
    mutationFn: ({ type, fichier }: { type: string; fichier: File }) =>
      deposerPieceSociete(type, fichier),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: CLE });
      toast({ title: "Pièce déposée" });
    },
    onError: (erreur) =>
      toast({
        title: "Dépôt impossible",
        description: messageDErreur(erreur),
        variant: "destructive",
      }),
  });

  const retrait = useMutation({
    mutationFn: (chemin: string) => retirerPieceSociete(chemin),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: CLE });
      toast({ title: "Pièce retirée" });
    },
    onError: (erreur) =>
      toast({
        title: "Retrait impossible",
        description: messageDErreur(erreur),
        variant: "destructive",
      }),
  });

  const ouvrir = async (fichier: FichierPiece) => {
    // Ouvert avant l'appel : après un await, le navigateur bloquerait la fenêtre.
    const fenetre = window.open("", "_blank");
    try {
      const url = await lienPieceSociete(fichier.chemin);
      if (fenetre) fenetre.location.href = url;
    } catch (erreur) {
      fenetre?.close();
      toast({
        title: "Ouverture impossible",
        description: messageDErreur(erreur),
        variant: "destructive",
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Pièces de la société</CardTitle>
        <CardDescription>
          {data
            ? resumePieces(data.manquantes)
            : "Les documents qui justifient la paie de cette société."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Chargement des pièces…</p>
        ) : isError || !data ? (
          <p className="text-sm text-destructive">
            Les pièces n&apos;ont pas pu être chargées. Rechargez la page.
          </p>
        ) : (
          <ul className="divide-y">
            {data.pieces.map((piece) => (
              <LignePiece
                key={piece.type}
                piece={piece}
                canEdit={canEdit}
                envoi={depot.isPending && depot.variables?.type === piece.type}
                onDeposer={(fichier) => depot.mutate({ type: piece.type, fichier })}
                onOuvrir={(fichier) => void ouvrir(fichier)}
                onRetirer={setARetirer}
              />
            ))}
          </ul>
        )}
      </CardContent>
      <AlertDialog open={aRetirer !== null} onOpenChange={(ouvert) => !ouvert && setARetirer(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Retirer cette pièce ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le fichier {aRetirer?.nom} sera supprimé de Martine. Vous pourrez le déposer de nouveau.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (aRetirer) retrait.mutate(aRetirer.chemin);
                setARetirer(null);
              }}
            >
              Retirer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
