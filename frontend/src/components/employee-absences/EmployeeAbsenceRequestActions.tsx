import { Download, Eye, MoreHorizontal } from 'lucide-react';
import type { AbsenceRequest } from '@/api/absences';
import { log } from '@/lib/logger';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useToast } from '@/components/ui/use-toast';
import { downloadBlob, openBlobInNewTab } from '@/lib/downloadBlob';

interface EmployeeAbsenceRequestActionsProps {
  absence: AbsenceRequest;
}

export function EmployeeAbsenceRequestActions({
  absence,
}: EmployeeAbsenceRequestActionsProps) {
  const { toast } = useToast();

  const handleDownloadAttachment = async () => {
    const signedUrl = absence.attachment_url;
    if (!signedUrl) {
      toast({
        title: 'Erreur',
        description: 'Aucun justificatif associé.',
        variant: 'destructive',
      });
      return;
    }
    try {
      const response = await fetch(signedUrl);
      if (!response.ok) throw new Error(`Erreur réseau: ${response.statusText}`);
      const blob = await response.blob();
      downloadBlob(blob, absence.filename || 'justificatif');
    } catch (error) {
      log.error('Erreur téléchargement justificatif:', error);
      toast({
        title: 'Erreur',
        description: 'Impossible de lancer le téléchargement.',
        variant: 'destructive',
      });
    }
  };

  const hasAttachment = Boolean(absence.attachment_url);
  if (!hasAttachment) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 gap-1">
            <MoreHorizontal className="h-4 w-4" />
            <span className="sr-only sm:not-sr-only sm:inline">Actions</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {hasAttachment && (
            <>
              <DropdownMenuItem asChild>
                <a
                  href={absence.attachment_url!}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Eye className="mr-2 h-4 w-4" />
                  Voir le justificatif
                </a>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleDownloadAttachment}>
                <Download className="mr-2 h-4 w-4" />
                Télécharger le justificatif
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Desktop : icônes rapides */}
      <div className="hidden gap-1 sm:flex">
        {hasAttachment && (
          <>
            <Button variant="outline" size="icon" className="h-8 w-8" asChild>
              <a
                href={absence.attachment_url!}
                target="_blank"
                rel="noopener noreferrer"
                title="Voir le justificatif"
              >
                <Eye className="h-4 w-4" />
              </a>
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => void handleDownloadAttachment()}
              title="Télécharger le justificatif"
            >
              <Download className="h-4 w-4" />
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
