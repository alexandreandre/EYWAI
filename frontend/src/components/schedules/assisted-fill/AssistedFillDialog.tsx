import { useCallback, useState } from 'react';
import { ListChecks, Loader2, Mic, Sparkles, Square } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useToast } from '@/components/ui/use-toast';
import { useSpeechDictation } from '@/hooks/useSpeechDictation';
import { cn } from '@/lib/utils';
import {
  parseScheduleInstruction,
  type AiCalendarProposal,
  type RosterEmployee,
} from '@/api/calendar';
import { AssistedFillProgress } from './AssistedFillProgress';
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
  /** Mode fiche collaborateur : tout est attribué à l'unique employé du roster. */
  singleEmployee?: boolean;
  /**
   * Quand l'analyse IA est restreinte à un sous-ensemble (ex. « À saisir »),
   * affiche le périmètre exact pour que l'utilisateur comprenne la portée.
   */
  targetSummary?: { count: number; names: string[] } | null;
  /**
   * Mode saisie collective : la consigne s'applique à TOUS les employés du
   * roster (les « À saisir »), sans avoir à citer de noms.
   */
  broadcast?: boolean;
}

export function AssistedFillDialog({
  open,
  onOpenChange,
  year,
  month,
  roster,
  onApplied,
  singleEmployee = false,
  targetSummary = null,
  broadcast = false,
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
  const targetName =
    singleEmployee && roster[0]
      ? `${roster[0].first_name} ${roster[0].last_name}`
      : null;

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
    if (dictation.isListening) dictation.stop();
    setIsAnalyzing(true);
    try {
      const result = await parseScheduleInstruction(
        year,
        month,
        instruction,
        roster,
        singleEmployee,
        broadcast,
      );
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
      <DialogContent
        className={cn(
          // max-h seul : le modal épouse son contenu (une revue à 1 salarié ne
          // flotte plus dans un écran vide) tout en restant plafonné.
          'flex max-h-[90dvh] w-full max-w-3xl translate-y-0 flex-col gap-0 overflow-hidden p-0 top-[5dvh]',
          proposal && 'max-w-4xl',
        )}
      >
        <DialogHeader className="shrink-0 space-y-1 border-b px-5 py-3">
          <DialogTitle className="flex items-center gap-2 text-base">
            <Sparkles className="h-4 w-4 text-primary" />
            {proposal
              ? `Revue — ${periodLabel}`
              : `Remplissage par IA — ${periodLabel}`}
          </DialogTitle>
          {!proposal && (
            <DialogDescription className="text-xs">
              {targetName ? (
                <>Consigne pour {targetName} — validation avant enregistrement.</>
              ) : (
                <>Consigne collective ou individuelle — validation avant enregistrement.</>
              )}
            </DialogDescription>
          )}
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-5 py-3">
        {proposal ? (
          <AssistedFillReview
            proposal={proposal}
            roster={roster}
            onApplied={handleApplied}
            onBack={() => setProposal(null)}
          />
        ) : isAnalyzing ? (
          <AssistedFillProgress />
        ) : (
          <div className="max-h-full space-y-2 overflow-y-auto pr-1">
            {targetSummary && targetSummary.count > 0 && !singleEmployee && (
              <div className="rounded-lg border border-primary/30 bg-primary/5 px-3 py-2.5 text-sm">
                <p className="flex items-center gap-1.5 font-medium text-foreground">
                  <ListChecks className="h-4 w-4 text-primary" />
                  Ciblé sur {targetSummary.count} collaborateur
                  {targetSummary.count > 1 ? 's' : ''} « À saisir »
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {broadcast ? (
                    <>
                      Inutile de citer les noms : décrivez l&apos;horaire une
                      fois, il sera appliqué à ces {targetSummary.count}{' '}
                      collaborateurs (et à eux seuls). Vous pourrez ajuster
                      chacun avant d&apos;enregistrer.
                    </>
                  ) : (
                    <>
                      Seuls ces collaborateurs seront reconnus par l&apos;IA.
                      Citez leur nom dans la consigne ; les autres sont ignorés.
                    </>
                  )}
                </p>
                <ScrollArea className="mt-2 max-h-28 rounded-md border bg-background/60">
                  <ul className="divide-y px-2 py-1">
                    {targetSummary.names.map((name) => (
                      <li
                        key={name}
                        className="py-1 text-[11px] text-foreground/80"
                      >
                        {name}
                      </li>
                    ))}
                  </ul>
                </ScrollArea>
              </div>
            )}

            <div
              className={cn(
                'group relative rounded-xl border bg-card shadow-sm transition-colors focus-within:border-primary/60 focus-within:ring-1 focus-within:ring-primary/20',
                dictation.isListening && 'border-primary/60 ring-1 ring-primary/20',
              )}
            >
              <Textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder={
                  targetName
                    ? 'Ex : a fait 8h du lundi au jeudi et 7h le vendredi (heures faites). La semaine prochaine, prévu 7h tous les jours (heures prévues).'
                    : broadcast
                      ? 'Ex : tout le monde a fait 7h du lundi au vendredi, et 4h les samedis (heures faites). Inutile de citer les noms.'
                      : 'Ex : Paul Martin a fait 8h du lundi au jeudi et 7h le vendredi (heures faites). Sophie Durand est prévue 7h tous les jours la semaine prochaine (heures prévues).'
                }
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
        </div>
      </DialogContent>
    </Dialog>
  );
}
