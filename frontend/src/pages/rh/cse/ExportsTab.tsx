// frontend/src/pages/cse/ExportsTab.tsx

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Download, FileSpreadsheet, FileText, Loader2 } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import {
  exportElectedMembers,
  exportDelegationHours,
  exportMeetingsHistory,
  exportMinutesAnnual,
  exportElectionCalendar,
  getElectionCycles,
} from "@/api/cse";
import { getMonthPeriod } from "@/lib/csePeriod";
import { downloadBlob, openBlobInNewTab, createBlobPreviewUrl } from '@/lib/downloadBlob';

const MONTH_OPTIONS = Array.from({ length: 12 }, (_, i) => ({
  value: String(i),
  label: new Date(2000, i, 1).toLocaleDateString("fr-FR", { month: "long" }),
}));

export default function ExportsTab() {
  const { toast } = useToast();
  const [exporting, setExporting] = useState<string | null>(null);
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [monthIndex, setMonthIndex] = useState(now.getMonth());
  const [minutesYear, setMinutesYear] = useState(now.getFullYear());
  const [electionCycleId, setElectionCycleId] = useState<string>("all");

  const { periodStart, periodEnd, label: periodLabel } = getMonthPeriod(year, monthIndex);

  const { data: cycles = [] } = useQuery({
    queryKey: ["cse", "election-cycles", "exports"],
    queryFn: () => getElectionCycles(),
  });

  const handleExport = async (
    exportFn: () => Promise<Blob>,
    filename: string,
    exportType: string,
  ) => {
    try {
      setExporting(exportType);
      const blob = await exportFn();
      downloadBlob(blob, filename);
      document.body.removeChild(a);
      toast({
        title: "Export réussi",
        description: `Le fichier ${filename} a été téléchargé.`,
      });
    } catch (error: unknown) {
      const msg =
        error && typeof error === "object" && "message" in error
          ? String((error as { message?: string }).message)
          : "Erreur lors de l'export";
      toast({
        title: "Erreur",
        description: msg,
        variant: "destructive",
      });
    } finally {
      setExporting(null);
    }
  };

  const yearOptions = [now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            Exports et périodes
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-4 rounded-lg border p-4 bg-muted/30">
            <div>
              <Label className="text-xs text-muted-foreground">
                Période (délégation & réunions)
              </Label>
              <div className="flex gap-2 mt-1">
                <Select value={String(monthIndex)} onValueChange={(v) => setMonthIndex(Number(v))}>
                  <SelectTrigger className="w-[130px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MONTH_OPTIONS.map((m) => (
                      <SelectItem key={m.value} value={m.value}>
                        {m.label.charAt(0).toUpperCase() + m.label.slice(1)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
                  <SelectTrigger className="w-[90px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {yearOptions.map((y) => (
                      <SelectItem key={y} value={String(y)}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <p className="text-xs text-muted-foreground mt-1">{periodLabel}</p>
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Année PV annuels</Label>
              <Select
                value={String(minutesYear)}
                onValueChange={(v) => setMinutesYear(Number(v))}
              >
                <SelectTrigger className="w-[100px] mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {yearOptions.map((y) => (
                    <SelectItem key={y} value={String(y)}>
                      {y}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Cycle électoral (export)</Label>
              <Select value={electionCycleId} onValueChange={setElectionCycleId}>
                <SelectTrigger className="w-[200px] mt-1">
                  <SelectValue placeholder="Tous" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tous les cycles</SelectItem>
                  {cycles.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.cycle_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h3 className="font-semibold">Base des élus</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Export Excel de tous les élus CSE actifs
                    </p>
                  </div>
                  <Button
                    onClick={() =>
                      handleExport(
                        () => exportElectedMembers(),
                        `base_elus_${now.getFullYear()}.xlsx`,
                        "elected-members",
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

            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h3 className="font-semibold">Heures de délégation</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Mois en cours : {periodLabel}
                    </p>
                  </div>
                  <Button
                    onClick={() =>
                      handleExport(
                        () => exportDelegationHours(periodStart, periodEnd),
                        `delegation_heures_${year}_${monthIndex + 1}.xlsx`,
                        "delegation-hours",
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

            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h3 className="font-semibold">Historique des réunions</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Réunions sur la période : {periodLabel}
                    </p>
                  </div>
                  <Button
                    onClick={() =>
                      handleExport(
                        () => exportMeetingsHistory(periodStart, periodEnd),
                        `reunions_${year}_${monthIndex + 1}.xlsx`,
                        "meetings-history",
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

            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h3 className="font-semibold">PV annuels</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      PDF des procès-verbaux — année {minutesYear}
                    </p>
                  </div>
                  <Button
                    onClick={() =>
                      handleExport(
                        () => exportMinutesAnnual(minutesYear),
                        `pv_annuels_${minutesYear}.pdf`,
                        "minutes-annual",
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

            <Card className="sm:col-span-2">
              <CardContent className="pt-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h3 className="font-semibold">Calendrier électoral</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      PDF / Excel des obligations
                      {electionCycleId !== "all"
                        ? ` — ${cycles.find((c) => c.id === electionCycleId)?.cycle_name ?? ""}`
                        : " — tous les cycles"}
                    </p>
                  </div>
                  <Button
                    onClick={() =>
                      handleExport(
                        () =>
                          exportElectionCalendar(
                            electionCycleId !== "all" ? electionCycleId : undefined,
                          ),
                        `calendrier_electoral_${electionCycleId !== "all" ? electionCycleId : year}.pdf`,
                        "election-calendar",
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
