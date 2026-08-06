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
  Percent,
  RefreshCw,
  Search,
  Upload,
} from "lucide-react";

import { RhPageHeader } from "@/components/layout";
import { SharkFinLoader } from "@/components/SharkFinLoader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
import { PasStatutBadge } from "@/features/pas-rates/components/PasStatutBadge";
import {
  exportPasRates,
  getPasRates,
  pasRatesErrorMessage,
  type PasLigne,
  type PasStatut,
} from "@/api/pasRates";
import { cn } from "@/lib/utils";

type Filtre = "tous" | PasStatut;

const COMPTEURS: { cle: Filtre; label: string; aide: string; accent: string }[] = [
  {
    cle: "tous",
    label: "Salariés",
    aide: "Effectif suivi",
    accent: "border-border",
  },
  {
    cle: "manquant",
    label: "Sans taux",
    aide: "Bulletin à 0 % par défaut",
    accent: "border-danger/50 bg-danger/5",
  },
  {
    cle: "a_rafraichir",
    label: "À rafraîchir",
    aide: "Taux de plus de deux mois",
    accent: "border-warning/50 bg-warning/5",
  },
  {
    cle: "bareme",
    label: "Au barème",
    aide: "En attente du taux DGFiP",
    accent: "border-border bg-muted/40",
  },
  {
    cle: "a_jour",
    label: "À jour",
    aide: "Taux DGFiP récent",
    accent: "border-success/50 bg-success/5",
  },
];

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

  const [filtre, setFiltre] = useState<Filtre>("tous");
  const [recherche, setRecherche] = useState("");
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
  const compteurs = data?.compteurs ?? {};

  const affichees = useMemo(() => {
    let items = lignes;
    if (filtre !== "tous") {
      items = items.filter((l) => l.statut === filtre);
    }
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
  }, [lignes, filtre, recherche]);

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

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {COMPTEURS.map((compteur) => {
          const valeur =
            compteur.cle === "tous"
              ? compteurs.total ?? 0
              : compteurs[compteur.cle] ?? 0;
          const actif = filtre === compteur.cle;
          return (
            <button
              key={compteur.cle}
              type="button"
              onClick={() => setFiltre(actif && compteur.cle !== "tous" ? "tous" : compteur.cle)}
              className={cn(
                "rounded-lg border p-4 text-left transition-colors hover:bg-muted/60",
                compteur.accent,
                actif && "ring-2 ring-primary ring-offset-1",
              )}
            >
              <p className="text-2xl font-semibold tabular-nums">{valeur}</p>
              <p className="text-sm font-medium">{compteur.label}</p>
              <p className="text-xs text-muted-foreground">{compteur.aide}</p>
            </button>
          );
        })}
      </div>

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
              <p className="mt-1 text-sm">Modifiez le filtre ou la recherche.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[26%]">Collaborateur</TableHead>
                  <TableHead className="w-[12%]">Taux</TableHead>
                  <TableHead className="w-[22%]">Origine</TableHead>
                  <TableHead className="w-[18%]">Période du taux</TableHead>
                  <TableHead className="w-[16%]">Statut</TableHead>
                  <TableHead className="w-[6%]" />
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
                    <TableCell>
                      <PasStatutBadge
                        statut={ligne.statut}
                        libelle={ligne.statut_libelle}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
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
    </div>
  );
}
