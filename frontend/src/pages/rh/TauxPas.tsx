// Page RH : suivi des taux de prélèvement à la source.
//
// Le taux n'est pas une décision de l'employeur : la DGFiP le renvoie après le
// dépôt d'une DSN. Cet écran montre donc moins « le taux » que sa fraîcheur et
// sa provenance — c'est là que se logent les erreurs de prélèvement.

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronRight,
  Download,
  Loader2,
  Pencil,
  Percent,
  RefreshCw,
  Search,
  Upload,
} from "lucide-react";

import { RhPageHeader } from "@/components/layout";
import { SharkFinLoader } from "@/components/SharkFinLoader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import { useCompany } from "@/contexts/CompanyContext";
import { PasImportDialog } from "@/features/pas-rates/components/PasImportDialog";
import {
  exportPasRates,
  getPasRates,
  pasRatesErrorMessage,
  setPasRateManuel,
  type PasLigne,
} from "@/api/pasRates";

function formatTaux(valeur: number | null): string {
  return valeur == null ? "—" : `${valeur.toFixed(2).replace(".", ",")} %`;
}

function formatPeriode(periode: string | null): string {
  if (!periode) return "Inconnue";
  const [annee, mois] = periode.split("-");
  const libelles = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
  ];
  const index = Number(mois) - 1;
  return libelles[index] ? `${libelles[index]} ${annee}` : periode;
}

function messageErreur(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data
    ?.detail;
  if (typeof detail === "string") return detail;
  if (error instanceof Error && error.message) return error.message;
  return "Impossible de charger les taux. Vérifiez votre connexion puis réessayez.";
}

export default function TauxPas() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? "";

  const [recherche, setRecherche] = useState("");
  const [edition, setEdition] = useState<PasLigne | null>(null);
  const [tauxSaisi, setTauxSaisi] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [importOuvert, setImportOuvert] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["pas-rates", activeCompanyId],
    queryFn: async () => (await getPasRates()).data,
    enabled: !!activeCompanyId,
  });

  useEffect(() => {
    if (isError) {
      toast({
        title: "Erreur",
        description: messageErreur(error),
        variant: "destructive",
      });
    }
  }, [isError, error, toast]);

  const lignes = useMemo<PasLigne[]>(() => data?.lignes ?? [], [data]);

  const affichees = useMemo(() => {
    let items = lignes;
    const terme = recherche.trim().toLowerCase();
    if (terme) {
      items = items.filter(
        (l) =>
          l.nom.toLowerCase().includes(terme) ||
          l.prenom.toLowerCase().includes(terme) ||
          l.matricule.toLowerCase().includes(terme),
      );
    }
    return items;
  }, [lignes, recherche]);

  const ouvrirEdition = (ligne: PasLigne) => {
    setEdition(ligne);
    setTauxSaisi(ligne.taux == null ? "" : String(ligne.taux));
  };

  const handleSaveTaux = async () => {
    if (!edition) return;
    const valeur = parseFloat(tauxSaisi.replace(",", "."));
    if (!Number.isFinite(valeur) || valeur < 0 || valeur > 100) {
      toast({
        title: "Erreur",
        description: "Indiquez un taux entre 0 et 100.",
        variant: "destructive",
      });
      return;
    }
    setIsSaving(true);
    try {
      await setPasRateManuel(edition.employee_id, valeur);
      toast({ title: "Succès", description: "Taux enregistré." });
      setEdition(null);
      await refetch();
    } catch (saveError) {
      toast({
        title: "Erreur",
        description: await pasRatesErrorMessage(saveError),
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await exportPasRates();
    } catch (exportError) {
      toast({
        title: "Export impossible",
        description: await pasRatesErrorMessage(exportError),
        variant: "destructive",
      });
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <RhPageHeader
        title="Taux de prélèvement à la source"
        description={`Le taux appliqué sur les bulletins vient de la DGFiP, qui le renvoie après le dépôt de chaque déclaration${
          activeCompany?.company_name ? ` — ${activeCompany.company_name}` : ""
        }.`}
      />

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col items-stretch justify-between gap-4 sm:flex-row sm:items-center">
            <div className="relative max-w-sm flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Rechercher un salarié…"
                value={recherche}
                onChange={(e) => setRecherche(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex items-center gap-3">
              <Button
                type="button"
                variant="outline"
                className="gap-2"
                onClick={() => void handleExport()}
                disabled={isExporting || isLoading || lignes.length === 0}
              >
                {isExporting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                Exporter en Excel
              </Button>
              <Button type="button" className="gap-2" onClick={() => setImportOuvert(true)}>
                <Upload className="h-4 w-4" />
                Mettre à jour les taux
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <SharkFinLoader label="Chargement des taux…" />
          ) : isError ? (
            <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-center">
              <p className="text-sm font-medium text-destructive">Erreur de chargement</p>
              <p className="mt-1 text-sm text-muted-foreground">{messageErreur(error)}</p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-4 gap-2"
                onClick={() => void refetch()}
              >
                <RefreshCw className="h-4 w-4" />
                Réessayer
              </Button>
            </div>
          ) : lignes.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <Percent className="mb-4 h-12 w-12 opacity-50" />
              <p className="font-medium">Aucun salarié à suivre sur cette entreprise</p>
            </div>
          ) : affichees.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <Search className="mb-4 h-12 w-12 opacity-50" />
              <p className="font-medium">Aucun résultat</p>
              <p className="mt-1 text-sm">Modifiez la recherche.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[30%]">Collaborateur</TableHead>
                  <TableHead className="w-[16%]">Taux</TableHead>
                  <TableHead className="w-[26%]">Origine</TableHead>
                  <TableHead className="w-[18%]">Période du taux</TableHead>
                  <TableHead className="w-[10%]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {affichees.map((ligne) => (
                  <TableRow
                    key={ligne.employee_id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/employees/${ligne.employee_id}`)}
                  >
                    <TableCell>
                      <span className="font-medium">
                        {ligne.prenom} {ligne.nom}
                      </span>
                      {ligne.matricule ? (
                        <span className="ml-2 text-xs text-muted-foreground">
                          {ligne.matricule}
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell className="font-semibold tabular-nums">
                      {formatTaux(ligne.taux)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {ligne.type_libelle}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatPeriode(ligne.periode)}
                    </TableCell>
                    <TableCell className="text-right">
                      <span className="inline-flex items-center gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          title="Modifier le taux"
                          onClick={(e) => {
                            e.stopPropagation();
                            ouvrirEdition(ligne);
                          }}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <PasImportDialog
        open={importOuvert}
        onOpenChange={setImportOuvert}
        onApplied={() => void refetch()}
      />

      <Dialog open={!!edition} onOpenChange={(open) => !open && setEdition(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>
              Taux de {edition?.prenom} {edition?.nom}
            </DialogTitle>
            <p className="text-sm text-muted-foreground">
              Saisie manuelle, appliquée aux prochains bulletins jusqu'au prochain
              retour DGFiP.
            </p>
          </DialogHeader>
          <div className="grid gap-2 py-2">
            <Label htmlFor="taux-manuel">Taux (%)</Label>
            <Input
              id="taux-manuel"
              type="number"
              min="0"
              max="100"
              step="0.01"
              value={tauxSaisi}
              onChange={(e) => setTauxSaisi(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEdition(null)}>
              Annuler
            </Button>
            <Button onClick={() => void handleSaveTaux()} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
