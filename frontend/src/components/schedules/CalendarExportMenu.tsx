import { useState } from 'react';
import { ChevronDown, Download, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useToast } from '@/components/ui/use-toast';
import {
  exportOverviewCsv,
  exportOverviewPdf,
  exportOverviewXlsx,
  type EmployeeCalendarOverviewRow,
  type OverviewExportFormat,
} from '@/lib/schedulesOverview';

interface CalendarExportMenuProps {
  rows: EmployeeCalendarOverviewRow[];
  year: number;
  month: number;
}

export function CalendarExportMenu({ rows, year, month }: CalendarExportMenuProps) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);

  const run = async (format: OverviewExportFormat) => {
    if (rows.length === 0) {
      toast({
        title: 'Rien à exporter',
        description: 'Aucun calendrier affiché.',
        variant: 'destructive',
      });
      return;
    }
    setBusy(true);
    try {
      if (format === 'csv') {
        exportOverviewCsv(rows, year, month);
        toast({ title: 'Export', description: 'Fichier CSV téléchargé.' });
      } else if (format === 'xlsx') {
        await exportOverviewXlsx(rows, year, month);
        toast({ title: 'Export', description: 'Fichier Excel téléchargé.' });
      } else {
        exportOverviewPdf(rows, year, month);
        toast({ title: 'Export', description: 'Aperçu PDF ouvert pour impression.' });
      }
    } catch {
      toast({
        title: 'Export impossible',
        description: 'Le fichier n’a pas pu être généré.',
        variant: 'destructive',
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="outline" className="h-9" disabled={busy}>
          {busy ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Download className="mr-2 h-4 w-4" />
          )}
          Export
          <ChevronDown className="ml-1 h-4 w-4 opacity-70" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => void run('csv')}>CSV (.csv)</DropdownMenuItem>
        <DropdownMenuItem onClick={() => void run('xlsx')}>Excel (.xlsx)</DropdownMenuItem>
        <DropdownMenuItem onClick={() => void run('pdf')}>PDF</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
