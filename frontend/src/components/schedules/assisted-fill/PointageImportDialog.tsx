import { useRef, useState } from 'react';
import { Loader2, Sparkles, Upload } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';
import {
  extractTimesheet,
  type AiCalendarProposal,
  type RosterEmployee,
} from '@/api/calendar';
import { AssistedFillReview } from './AssistedFillReview';
import { aiFillErrorMessage } from './aiFillUtils';

const MONTHS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

const ACCEPTED = '.pdf,.jpg,.jpeg,.png,.webp,.tif,.tiff';

interface PointageImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  year: number;
  month: number;
  roster: RosterEmployee[];
  onApplied: () => void;
}

export function PointageImportDialog({
  open,
  onOpenChange,
  year,
  month,
  roster,
  onApplied,
}: PointageImportDialogProps) {
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [proposal, setProposal] = useState<AiCalendarProposal | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const periodLabel = `${MONTHS[month - 1]} ${year}`;

  const reset = () => {
    setFile(null);
    setProposal(null);
    setIsAnalyzing(false);
  };

  const handleClose = (next: boolean) => {
    if (!next) reset();
    onOpenChange(next);
  };

  const showProposal = (result: AiCalendarProposal) => {
    if (result.employees.length === 0) {
      toast({
        title: 'Aucune donnée détectée',
        description:
          result.warnings[0] ?? "L'IA n'a rien pu extraire. Essayez un autre relevé.",
        variant: 'destructive',
      });
      return;
    }
    setProposal(result);
  };

  const analyzeFile = async () => {
    if (!file) return;
    setIsAnalyzing(true);
    try {
      const result = await extractTimesheet(file, year, month, roster);
      showProposal(result);
    } catch (e) {
      toast({
        title: 'Analyse impossible',
        description: aiFillErrorMessage(e),
        variant: 'destructive',
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleApplied = () => {
    onApplied();
    handleClose(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5 text-primary" />
            Importer des pointages — {periodLabel}
          </DialogTitle>
          <DialogDescription>
            Importez un relevé de pointeuse (PDF ou image). L&apos;IA extrait les heures
            prévues et faites, vous validez avant enregistrement.
          </DialogDescription>
        </DialogHeader>

        {proposal ? (
          <AssistedFillReview
            proposal={proposal}
            roster={roster}
            onApplied={handleApplied}
            onBack={() => setProposal(null)}
          />
        ) : (
          <div className="space-y-3 pt-1">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                const dropped = e.dataTransfer.files?.[0];
                if (dropped) setFile(dropped);
              }}
              className={cn(
                'flex w-full flex-col items-center gap-2 rounded-lg border-2 border-dashed py-8 text-sm transition-colors',
                isDragging ? 'border-primary bg-primary/5' : 'border-muted-foreground/25',
              )}
            >
              <Upload className="h-7 w-7 text-muted-foreground" />
              {file ? (
                <span className="font-medium">{file.name}</span>
              ) : (
                <>
                  <span className="font-medium">Glissez un relevé ici, ou cliquez</span>
                  <span className="text-xs text-muted-foreground">
                    PDF, JPG ou PNG (max 15 Mo)
                  </span>
                </>
              )}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED}
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <div className="flex justify-end gap-2">
              {file && (
                <Button type="button" variant="ghost" onClick={() => setFile(null)}>
                  Retirer
                </Button>
              )}
              <Button
                type="button"
                onClick={() => void analyzeFile()}
                disabled={!file || isAnalyzing}
              >
                {isAnalyzing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="mr-2 h-4 w-4" />
                )}
                Analyser le relevé
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
