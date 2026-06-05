import { useCallback, useState } from 'react';
import { Loader2, Mic, Sparkles, Square } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import { useSpeechDictation } from '@/hooks/useSpeechDictation';
import { cn } from '@/lib/utils';
import {
  parseScheduleInstruction,
  type AiCalendarProposal,
  type RosterEmployee,
} from '@/api/calendar';
import { AssistedFillReview } from './AssistedFillReview';
import { aiFillErrorMessage } from './aiFillUtils';

const MONTHS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

interface AssistedFillDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  year: number;
  month: number;
  roster: RosterEmployee[];
  onApplied: () => void;
}

export function AssistedFillDialog({
  open,
  onOpenChange,
  year,
  month,
  roster,
  onApplied,
}: AssistedFillDialogProps) {
  const { toast } = useToast();
  const [instruction, setInstruction] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [proposal, setProposal] = useState<AiCalendarProposal | null>(null);

  const appendTranscript = useCallback((text: string) => {
    setInstruction((prev) => (prev ? `${prev} ${text}` : text));
  }, []);

  const dictation = useSpeechDictation(appendTranscript);

  const periodLabel = `${MONTHS[month - 1]} ${year}`;

  const reset = () => {
    setInstruction('');
    setProposal(null);
    setIsAnalyzing(false);
  };

  const handleClose = (next: boolean) => {
    if (!next) {
      if (dictation.isListening) dictation.stop();
      reset();
    }
    onOpenChange(next);
  };

  const showProposal = (result: AiCalendarProposal) => {
    if (result.employees.length === 0) {
      toast({
        title: 'Aucune donnée détectée',
        description:
          result.warnings[0] ?? "L'IA n'a rien pu extraire. Reformulez votre consigne.",
        variant: 'destructive',
      });
      return;
    }
    setProposal(result);
  };

  const analyzeText = async () => {
    if (!instruction.trim()) return;
    setIsAnalyzing(true);
    try {
      const result = await parseScheduleInstruction(year, month, instruction, roster);
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
            <Sparkles className="h-5 w-5 text-primary" />
            Remplissage par IA — {periodLabel}
          </DialogTitle>
          <DialogDescription>
            Dictez ou écrivez vos consignes de planning. L&apos;IA distingue les heures
            prévues des heures faites, vous validez avant enregistrement.
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
          <div className="space-y-2 pt-1">
            <div
              className={cn(
                'group relative rounded-xl border bg-card shadow-sm transition-colors focus-within:border-primary/60 focus-within:ring-1 focus-within:ring-primary/20',
                dictation.isListening && 'border-primary/60 ring-1 ring-primary/20',
              )}
            >
              <Textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="Ex : Paul Martin a fait 8h du lundi au jeudi et 7h le vendredi (heures faites). Sophie Durand est prévue 7h tous les jours la semaine prochaine (heures prévues)."
                rows={6}
                className="resize-none border-0 bg-transparent px-4 pt-4 pb-16 text-sm shadow-none focus-visible:ring-0"
              />

              <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 px-3 py-3">
                <div className="pointer-events-auto flex items-center gap-2">
                  {dictation.isSupported && (
                    <button
                      type="button"
                      onClick={() =>
                        dictation.isListening ? dictation.stop() : dictation.start()
                      }
                      aria-label={dictation.isListening ? 'Arrêter la dictée' : 'Démarrer la dictée'}
                      className={cn(
                        'flex h-9 w-9 items-center justify-center rounded-full border transition-all',
                        dictation.isListening
                          ? 'border-primary bg-primary text-primary-foreground shadow-[0_0_0_4px] shadow-primary/15'
                          : 'border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-foreground',
                      )}
                    >
                      {dictation.isListening ? (
                        <Square className="h-4 w-4 fill-current" />
                      ) : (
                        <Mic className="h-4 w-4" />
                      )}
                    </button>
                  )}
                  {dictation.isListening ? (
                    <span className="flex items-center gap-1.5 text-xs font-medium text-primary">
                      <span className="relative flex h-2 w-2">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/60" />
                        <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
                      </span>
                      Écoute en cours…
                    </span>
                  ) : (
                    dictation.isSupported && (
                      <span className="text-xs text-muted-foreground">
                        Cliquez sur le micro pour dicter
                      </span>
                    )
                  )}
                </div>

                <div className="pointer-events-auto">
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => void analyzeText()}
                    disabled={!instruction.trim() || isAnalyzing}
                  >
                    {isAnalyzing ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="mr-2 h-4 w-4" />
                    )}
                    Analyser
                  </Button>
                </div>
              </div>
            </div>

            {dictation.error && (
              <p className="px-1 text-xs text-destructive">{dictation.error}</p>
            )}
            {!dictation.isSupported && (
              <p className="px-1 text-xs text-muted-foreground">
                La dictée vocale n&apos;est pas disponible sur ce navigateur (Chrome ou Edge
                recommandés). Vous pouvez saisir votre consigne au clavier.
              </p>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
