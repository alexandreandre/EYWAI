// frontend/src/pages/cse/ExportsTab.tsx
// Onglet Exports

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Download, FileSpreadsheet, FileText, Loader2 } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import {
  exportElectedMembers,
  exportDelegationHours,
  exportMeetingsHistory,
  exportMinutesAnnual,
  exportElectionCalendar,
} from "@/api/cse";

export default function ExportsTab() {
  const { toast } = useToast();
  const [exporting, setExporting] = useState<string | null>(null);

  const handleExport = async (
    exportFn: () => Promise<Blob>,
    filename: string,
    exportType: string
  ) => {
    try {
      setExporting(exportType);
      const blob = await exportFn();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast({
        title: "Export réussi",
        description: `Le fichier ${filename} a été téléchargé.`,
      });
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error.message || "Erreur lors de l'export",
        variant: "destructive",
      });
    } finally {
      setExporting(null);
    }
  };

  const now = new Date();
  const currentYear = now.getFullYear();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Exports disponibles</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            {/* Export base élus */}
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">Base des élus</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Export Excel de tous les élus CSE
                    </p>
                  </div>
                  <Button
                    onClick={() =>
                      handleExport(
                        () => exportElectedMembers(),
                        `base_elus_${currentYear}.xlsx`,
                        "elected-members"
                      )
                    }
                    disabled={exporting === "elected-members"}
                  >
                    {exporting === "elected-members" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <FileSpreadsheet className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Export heures délégation */}
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">Heures de délégation</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Export Excel des heures consommées
                    </p>
                  </div>
                  <Button
                    onClick={() =>
                      handleExport(
                        () => exportDelegationHours(monthStart, monthEnd),
                        `delegation_heures_${currentYear}_${now.getMonth() + 1}.xlsx`,
                        "delegation-hours"
                      )
                    }
                    disabled={exporting === "delegation-hours"}
                  >
                    {exporting === "delegation-hours" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <FileSpreadsheet className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Export historique réunions */}
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">Historique des réunions</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Export Excel de toutes les réunions
                    </p>
                  </div>
                  <Button
                    onClick={() =>
                      handleExport(
                        () => exportMeetingsHistory(monthStart, monthEnd),
                        `reunions_${currentYear}_${now.getMonth() + 1}.xlsx`,
                        "meetings-history"
                      )
                    }
                    disabled={exporting === "meetings-history"}
                  >
                    {exporting === "meetings-history" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <FileSpreadsheet className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Export PV annuels */}
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">PV annuels</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Export PDF des procès-verbaux de l'année
                    </p>
                  </div>
                  <Button
                    onClick={() =>
                      handleExport(
                        () => exportMinutesAnnual(currentYear),
                        `pv_annuels_${currentYear}.pdf`,
                        "minutes-annual"
                      )
                    }
                    disabled={exporting === "minutes-annual"}
                  >
                    {exporting === "minutes-annual" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <FileText className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Export calendrier électoral */}
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">Calendrier électoral</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Export PDF/Excel du calendrier des obligations
                    </p>
                  </div>
                  <Button
                    onClick={() =>
                      handleExport(
                        () => exportElectionCalendar(),
                        `calendrier_electoral_${currentYear}.pdf`,
                        "election-calendar"
                      )
                    }
                    disabled={exporting === "election-calendar"}
                  >
                    {exporting === "election-calendar" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <FileText className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
