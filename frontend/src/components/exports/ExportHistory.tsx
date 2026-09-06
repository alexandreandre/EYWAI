// src/components/exports/ExportHistory.tsx
// Historique des exports - ÉTAPE 2 : Utilisation des données réelles

import { log } from '@/lib/logger';
import { showErrorToast } from '@/lib/errorMessages';
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { exportsLiveQueryOptions } from "@/lib/exportsQuery";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { History, Loader2, Download } from "lucide-react";
import { SharkFinLoader } from "@/components/SharkFinLoader";
import { ExportCardRefreshOverlay } from "@/components/exports/ExportCardRefreshOverlay";
import {
  getExportHistory,
  ExportHistoryEntry,
  listExportDownloadFiles,
  ExportType,
} from "@/api/exports";
import { downloadBlob } from '@/lib/downloadBlob';

const exportTypeLabels: Record<string, string> = {
  // Paie & Comptabilité
  journal_paie: "Journal de paie",
  od_salaires: "OD Salaires",
  od_charges_sociales: "OD Charges sociales",
  od_pas: "OD PAS",
  od_globale: "OD Globale de paie",
  export_cabinet_generique: "Export format comptable générique",
  export_cabinet_quadra: "Export format Quadra",
  export_cabinet_sage: "Export format Sage",
  // Déclarations
  dsn_mensuelle: "DSN mensuelle",
  // Paiements
  virement_salaires: "Virement salaires",
  virement_acomptes: "Virement acomptes",
  recapitulatif_montants: "Récapitulatif des montants",
  // Exports RH
  charges_sociales: "Charges sociales par caisse",
  conges_absences: "Congés payés / Absences",
  provision_cp: "Provision congés payés",
  notes_frais: "Notes de frais",
  acomptes: "Acomptes & avances",
  saisies: "Saisies sur salaire",
  fec: "FEC",
  prets_employeur: "Prêts employeur",
  paiement_organismes: "Paiement organismes",
  attestations_annexes: "Attestations & annexes",
  // Anciens formats (pour compatibilité)
  ecritures_comptables: "Écritures comptables",
};

interface ExportHistoryProps {
  exportType?: string;
  hideHeader?: boolean;
}

export function ExportHistory({ exportType, hideHeader = false }: ExportHistoryProps) {
  const [downloadingIds, setDownloadingIds] = useState<Set<string>>(new Set());

  const {
    data: historyResponse,
    isLoading,
    isFetching,
    error: queryError,
  } = useQuery({
    queryKey: ["export-history", exportType ?? "all"],
    queryFn: () => getExportHistory(exportType as ExportType | undefined),
    ...exportsLiveQueryOptions,
  });

  const history = historyResponse?.exports ?? [];
  const error =
    queryError && typeof queryError === "object" && "response" in queryError
      ? String((queryError as { response?: { data?: { detail?: string } } }).response?.data?.detail)
      : queryError
        ? "Erreur lors du chargement de l'historique"
        : null;

  const handleDownload = async (exportId: string, exportType: string, period: string) => {
    setDownloadingIds((prev) => new Set(prev).add(exportId));
    try {
      const files = await listExportDownloadFiles(exportId);
      if (files.length === 0) {
        throw new Error("Aucun fichier disponible");
      }

      for (const file of files) {
        const fileResponse = await fetch(file.download_url);
        if (!fileResponse.ok) {
          throw new Error(`Erreur HTTP: ${fileResponse.statusText}`);
        }
        const blob = await fileResponse.blob();
        const fallbackName = `${exportType}_${period.replace("-", "_")}`;
        const filename =
          file.filename && file.filename !== "export" ? file.filename : fallbackName;
        downloadBlob(blob, filename);
      }
    } catch (err: any) {
      log.error("Erreur lors du téléchargement:", err);
      showErrorToast(err, {
        title: 'Téléchargement impossible',
        fallback: "Le téléchargement de l'export a échoué. Réessayez.",
      });
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
    <Card className="relative">
      <ExportCardRefreshOverlay
        visible={isFetching && !isLoading}
        label="Actualisation de l'historique…"
      />
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
          <SharkFinLoader className="min-h-[160px]" label="Chargement de l'historique…" />
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
                      title={
                        item.files_count > 1
                          ? `Télécharger ${item.files_count} fichiers`
                          : "Télécharger l'export"
                      }
                    >
                      {downloadingIds.has(item.id) ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <span className="relative inline-flex">
                          <Download className="h-4 w-4" />
                          {item.files_count > 1 ? (
                            <span className="bg-primary text-primary-foreground absolute -right-2 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full px-0.5 text-[10px]">
                              {item.files_count}
                            </span>
                          ) : null}
                        </span>
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

