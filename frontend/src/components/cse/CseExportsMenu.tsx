import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Download, FileSpreadsheet, FileText, Loader2, ChevronDown } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import {
  exportElectedMembers,
  exportDelegationHours,
  exportMeetingsHistory,
  exportMinutesAnnual,
  exportElectionCalendar,
} from "@/api/cse";
import { getCurrentMonthPeriod } from "@/lib/csePeriod";
async function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

interface CseExportsMenuProps {
  onOpenExportsTab?: () => void;
}

export function CseExportsMenu({ onOpenExportsTab }: CseExportsMenuProps) {
  const { toast } = useToast();
  const [exporting, setExporting] = useState<string | null>(null);
  const now = new Date();
  const currentYear = now.getFullYear();
  const { periodStart, periodEnd, label: periodLabel } = getCurrentMonthPeriod();

  const runExport = async (
    key: string,
    fn: () => Promise<Blob>,
    filename: string,
  ) => {
    try {
      setExporting(key);
      const blob = await fn();
      await downloadBlob(blob, filename);
      toast({ title: "Export réussi", description: filename });
    } catch (error: unknown) {
      const msg =
        error && typeof error === "object" && "message" in error
          ? String((error as { message?: string }).message)
          : "Erreur lors de l'export";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    } finally {
      setExporting(null);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          {exporting ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Download className="h-4 w-4 mr-2" />
          )}
          Exports
          <ChevronDown className="h-4 w-4 ml-1 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>Exports rapides</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          disabled={!!exporting}
          onClick={() =>
            runExport("elected", () => exportElectedMembers(), `base_elus_${currentYear}.xlsx`)
          }
        >
          <FileSpreadsheet className="h-4 w-4 mr-2" />
          Base des élus
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={!!exporting}
          onClick={() =>
            runExport(
              "delegation",
              () => exportDelegationHours(periodStart, periodEnd),
              `delegation_heures_${currentYear}_${now.getMonth() + 1}.xlsx`,
            )
          }
        >
          <FileSpreadsheet className="h-4 w-4 mr-2" />
          Délégation ({periodLabel})
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={!!exporting}
          onClick={() =>
            runExport(
              "meetings",
              () => exportMeetingsHistory(periodStart, periodEnd),
              `reunions_${currentYear}_${now.getMonth() + 1}.xlsx`,
            )
          }
        >
          <FileSpreadsheet className="h-4 w-4 mr-2" />
          Réunions ({periodLabel})
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={!!exporting}
          onClick={() =>
            runExport(
              "minutes",
              () => exportMinutesAnnual(currentYear),
              `pv_annuels_${currentYear}.pdf`,
            )
          }
        >
          <FileText className="h-4 w-4 mr-2" />
          PV annuels {currentYear}
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={!!exporting}
          onClick={() =>
            runExport(
              "election",
              () => exportElectionCalendar(),
              `calendrier_electoral_${currentYear}.pdf`,
            )
          }
        >
          <FileText className="h-4 w-4 mr-2" />
          Calendrier électoral
        </DropdownMenuItem>
        {onOpenExportsTab && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onOpenExportsTab}>
              Tous les exports et options…
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
