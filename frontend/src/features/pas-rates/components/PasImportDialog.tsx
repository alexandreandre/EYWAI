// Dépôt d'un fichier de taux : aperçu d'abord, application ensuite.
//
// Les RH voient ce qui va changer, salarié par salarié, avant que quoi que ce
// soit ne soit écrit. Le fichier est renvoyé à l'application : c'est le serveur
// qui relit et décide, pas cet écran.

import { useState } from "react";
import { AlertTriangle, ArrowRight, FileUp, Loader2, Upload } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import {
  applyPasRates,
  pasRatesErrorMessage,
  previewPasRates,
  type PasApercu,
  type PasApercuLigne,
  type PasSource,
} from "@/api/pasRates";
import { INTRO_IMPORT_PAS, SOURCES_IMPORT_PAS, bilanImportPas } from '@/features/pas-rates/lib/importPas';
import { accord, pluriel } from '@/lib/pluriel';

interface PasImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApplied: () => void;
}

function formatTaux(valeur: number | null): string {
  return valeur == null ? "—" : `${valeur.toFixed(2).replace(".", ",")} %`;
}

function LigneChangement({ ligne }: { ligne: PasApercuLigne }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b py-2 text-sm last:border-b-0">
      <span className="min-w-0 flex-1 truncate font-medium">
        {ligne.nom} {ligne.prenom}
      </span>
      <span className="flex shrink-0 items-center gap-2 tabular-nums">
        <span className="text-muted-foreground">{formatTaux(ligne.taux_actuel)}</span>
        <ArrowRight className="h-3 w-3 text-muted-foreground" />
        <span className="font-semibold">{formatTaux(ligne.taux_fichier)}</span>
      </span>
      <Badge variant="outline" className="shrink-0">
        {ligne.type_fichier_libelle}
      </Badge>
    </div>
  );
}

export function PasImportDialog({ open, onOpenChange, onApplied }: PasImportDialogProps) {
  const { toast } = useToast();
  const [source, setSource] = useState<PasSource>("dsn");
  const [file, setFile] = useState<File | null>(null);
  const [apercu, setApercu] = useState<PasApercu | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  // Échecs de l'application : ils restent dans la fenêtre jusqu'à « Fermer ».
  const [bilan, setBilan] = useState<ReturnType<typeof bilanImportPas>>(null);

  const reinitialiser = () => {
    setFile(null);
    setApercu(null);
    setBilan(null);
    setIsLoading(false);
    setIsApplying(false);
  };

  const fermer = (ouvert: boolean) => {
    if (!ouvert) reinitialiser();
    onOpenChange(ouvert);
  };

  const choisirFichier = async (selection: File | null) => {
    setFile(selection);
    setApercu(null);
    if (!selection) return;
    setIsLoading(true);
    try {
      setApercu(await previewPasRates(selection, source));
    } catch (error) {
      toast({
        title: "Fichier refusé",
        description: await pasRatesErrorMessage(error),
        variant: "destructive",
      });
      setFile(null);
    } finally {
      setIsLoading(false);
    }
  };

  const appliquer = async () => {
    if (!file) return;
    setIsApplying(true);
    try {
      const resultat = await applyPasRates(file, source);
      onApplied();
      const echecs = bilanImportPas(resultat);
      if (echecs) {
        // Ne pas fermer : la liste des échecs et leur raison restent lisibles.
        setBilan(echecs);
        setApercu(null);
        return;
      }
      toast({
        title: `${resultat.appliques} taux mis à jour`,
        description: `Période ${resultat.periode}.`,
      });
      fermer(false);
    } catch (error) {
      toast({
        title: "Application impossible",
        description: await pasRatesErrorMessage(error),
        variant: "destructive",
      });
    } finally {
      setIsApplying(false);
    }
  };

  const changements = apercu?.lignes.filter(
    (l) => l.nature === "nouveau" || l.nature === "modifie",
  );
  const compteurs = apercu?.compteurs ?? {};

  return (
    <Dialog open={open} onOpenChange={fermer}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Mettre à jour les taux</DialogTitle>
          <DialogDescription>
            {INTRO_IMPORT_PAS}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="pas-source">Nature du fichier</Label>
            <Select
              value={source}
              onValueChange={(v) => {
                setSource(v as PasSource);
                reinitialiser();
              }}
            >
              <SelectTrigger id="pas-source">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SOURCES_IMPORT_PAS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {SOURCES_IMPORT_PAS.find((o) => o.value === source)?.aide}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="pas-fichier">Fichier</Label>
            <label
              htmlFor="pas-fichier"
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed px-4 py-6 text-sm hover:bg-muted/50"
            >
              <FileUp className="h-5 w-5 text-muted-foreground" />
              <span className={file ? "font-medium" : "text-muted-foreground"}>
                {file ? file.name : "Choisir un fichier .dsn ou .txt"}
              </span>
            </label>
            <input
              id="pas-fichier"
              type="file"
              accept=".dsn,.txt,.edi,text/plain"
              className="sr-only"
              onChange={(e) => void choisirFichier(e.target.files?.[0] ?? null)}
            />
          </div>

          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Lecture du fichier…
            </div>
          )}

          {bilan && (
            <div
              className="space-y-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm"
              role="alert"
              data-testid="pas-import-echecs"
            >
              <p className="flex items-center gap-2 font-medium text-destructive">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                {bilan.titre}
              </p>
              <ul className="max-h-48 space-y-1 overflow-y-auto">
                {bilan.lignes.map((ligne) => (
                  <li key={`${ligne.salarie}-${ligne.raison}`}>
                    <span className="font-medium">{ligne.salarie}</span> : {ligne.raison}
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted-foreground">{bilan.aide}</p>
            </div>
          )}

          {apercu && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Badge variant="outline">Période {apercu.periode}</Badge>
                <Badge variant="outline">SIREN {apercu.siren}</Badge>
                <span className="text-muted-foreground">
                  {pluriel(compteurs.inchange ?? 0, 'inchangé')}
                  {compteurs.hors_effectif
                    ? `, ${pluriel(compteurs.hors_effectif, 'sorti')} ${accord(compteurs.hors_effectif, 'ignoré')}`
                    : ""}
                  {compteurs.non_rapproche
                    ? `, ${compteurs.non_rapproche} sans fiche`
                    : ""}
                </span>
              </div>

              {apercu.avertissements.map((message) => (
                <div
                  key={message}
                  className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/5 p-3 text-sm"
                >
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                  <span>{message}</span>
                </div>
              ))}

              {changements && changements.length > 0 ? (
                <div className="max-h-64 overflow-y-auto rounded-md border px-4">
                  {changements.map((ligne) => (
                    <LigneChangement
                      key={`${ligne.employee_id ?? ligne.nom}-${ligne.prenom}`}
                      ligne={ligne}
                    />
                  ))}
                </div>
              ) : (
                <p className="rounded-md border bg-muted/30 p-4 text-sm text-muted-foreground">
                  Aucun changement : les taux en base correspondent déjà à ce fichier.
                </p>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          {bilan ? (
            <Button onClick={() => fermer(false)}>Fermer</Button>
          ) : (
          <>
          <Button variant="outline" onClick={() => fermer(false)} disabled={isApplying}>
            Annuler
          </Button>
          <Button
            onClick={() => void appliquer()}
            disabled={!changements || changements.length === 0 || isApplying}
            className="gap-2"
          >
            {isApplying ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            {changements && changements.length > 0
              ? `Appliquer ${changements.length} taux`
              : "Appliquer"}
          </Button>
          </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
