// src/components/exports/ExportHistory.tsx
// Historique des exports - ÉTAPE 2 : Utilisation des données réelles

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { History, Loader2, Download } from "lucide-react";
import { getExportHistory, ExportHistoryEntry, downloadExport, ExportType } from "@/api/exports";

const exportTypeLabels: Record<string, string> = {
  // Paie & Comptabilité
  journal_paie: "Journal de paie",
  od_salaires: "OD Salaires",
  od_charges_sociales: "OD Charges sociales",
  od_pas: "OD PAS",
  od_globale: "OD Globale de paie",
  export_cabinet_generique: "Export format cabinet générique",
  export_cabinet_quadra: "Export format Quadra",
  export_cabinet_sage: "Export format Sage",
  // Déclarations
  dsn_mensuelle: "DSN mensuelle",
  // Paiements
  virement_salaires: "Virement salaires",
  recapitulatif_montants: "Récapitulatif des montants",
  // Exports RH
  charges_sociales: "Charges sociales par caisse",
  conges_absences: "Congés payés / Absences",
  notes_frais: "Notes de frais",
  // Anciens formats (pour compatibilité)
  ecritures_comptables: "Écritures comptables",
};

interface ExportHistoryProps {
  exportType?: string;
  hideHeader?: boolean;
}

export function ExportHistory({ exportType, hideHeader = false }: ExportHistoryProps) {
  const [history, setHistory] = useState<ExportHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingIds, setDownloadingIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadHistory();
  }, [exportType]);

  const loadHistory = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await getExportHistory(exportType as ExportType | undefined);
      setHistory(response.exports);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Erreur lors du chargement de l'historique");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = async (exportId: string, exportType: string, period: string) => {
    setDownloadingIds((prev) => new Set(prev).add(exportId));
    try {
      const response = await downloadExport(exportId);
      const downloadUrl = response.download_url;

      // Télécharger le fichier
      const fileResponse = await fetch(downloadUrl);
      if (!fileResponse.ok) {
        throw new Error(`Erreur HTTP: ${fileResponse.statusText}`);
      }

      const blob = await fileResponse.blob();
      
      // Déterminer le nom du fichier
      const periodFormatted = period.replace("-", "_");
      const contentType = fileResponse.headers.get("content-type") || "";
      let extension = "xlsx";
      if (contentType.includes("csv") || contentType.includes("text/csv")) {
        extension = "csv";
      } else if (contentType.includes("zip") || contentType.includes("application/zip")) {
        extension = "zip";
      } else if (contentType.includes("xml")) {
        extension = "xml";
      }
      
      const filename = `${exportType}_${periodFormatted}.${extension}`;

      // Créer un lien de téléchargement
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error("Erreur lors du téléchargement:", err);
      alert(err.response?.data?.detail || "Erreur lors du téléchargement de l'export");
    } finally {
      setDownloadingIds((prev) => {
        const newSet = new Set(prev);
        newSet.delete(exportId);
        return newSet;
      });
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "generated":
        return <Badge variant="default">Généré</Badge>;
      case "previewed":
        return <Badge variant="secondary">Prévisualisé</Badge>;
      case "cancelled":
        return <Badge variant="outline">Annulé</Badge>;
      case "replaced":
        return <Badge variant="outline">Remplacé</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const formatPeriod = (period: string) => {
    try {
      const [year, month] = period.split("-");
      const monthNames = [
        "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
      ];
      return `${monthNames[parseInt(month) - 1]} ${year}`;
    } catch {
      return period;
    }
  };

  return (
    <Card>
      {!hideHeader && (
        <CardHeader>
          <div className="flex items-center gap-2">
            <History className="h-5 w-5" />
            <CardTitle>Historique des exports</CardTitle>
          </div>
          <CardDescription>
            {exportType 
              ? `Historique des exports de type "${exportTypeLabels[exportType] || exportType}".`
              : "Consultation de l'historique complet des exports générés. Tous les exports sont traçables et auditables."}
          </CardDescription>
        </CardHeader>
      )}
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="text-center py-8 text-destructive">
            <p>{error}</p>
          </div>
        ) : history.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <p>Aucun export généré pour le moment.</p>
            <p className="text-sm mt-2">L'historique s'affichera ici après la première génération d'export.</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type d'export</TableHead>
                <TableHead>Période</TableHead>
                <TableHead>Date de génération</TableHead>
                <TableHead>Utilisateur</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead className="text-center">Télécharger</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {history.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">
                    {exportTypeLabels[item.export_type] || item.export_type}
                  </TableCell>
                  <TableCell>{formatPeriod(item.period)}</TableCell>
                  <TableCell>
                    {new Date(item.generated_at).toLocaleString('fr-FR', {
                      day: '2-digit',
                      month: '2-digit',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </TableCell>
                  <TableCell>{item.generated_by_name || "Utilisateur"}</TableCell>
                  <TableCell>{getStatusBadge(item.status)}</TableCell>
                  <TableCell className="text-center">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDownload(item.id, item.export_type, item.period)}
                      disabled={downloadingIds.has(item.id) || item.status !== "generated"}
                      title="Télécharger l'export"
                    >
                      {downloadingIds.has(item.id) ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Download className="h-4 w-4" />
                      )}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

