import { useCallback, useRef, useState } from 'react';
import {
  FileText,
  Loader2,
  Mic,
  MicOff,
  Sparkles,
  Upload,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';
import { useSpeechDictation } from '@/hooks/useSpeechDictation';
import {
  extractTimesheet,
  parseScheduleInstruction,
  type AiCalendarProposal,
  type RosterEmployee,
} from '@/api/calendar';
import { AssistedFillReview } from './AssistedFillReview';

const MONTHS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

const ACCEPTED = '.pdf,.jpg,.jpeg,.png,.webp,.tif,.tiff';

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
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [proposal, setProposal] = useState<AiCalendarProposal | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const appendTranscript = useCallback((text: string) => {
    setInstruction((prev) => (prev ? `${prev} ${text}` : text));
  }, []);

  const dictation = useSpeechDictation(appendTranscript);

  const periodLabel = `${MONTHS[month - 1]} ${year}`;

  const reset = () => {
    setInstruction('');
    setFile(null);
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
          result.warnings[0] ?? "L'IA n'a rien pu extraire. Reformulez ou changez de document.",
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
        description: errorMessage(e),
        variant: 'destructive',
      });
    } finally {
      setIsAnalyzing(false);
    }
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
        description: errorMessage(e),
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
            Remplissage assisté — {periodLabel}
          </DialogTitle>
          <DialogDescription>
            Dictez, écrivez ou importez un relevé de pointeuse. L'IA distingue les heures
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
          <Tabs defaultValue="text">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="text">
                <FileText className="mr-1.5 h-4 w-4" /> Texte
              </TabsTrigger>
              <TabsTrigger value="voice">
                <Mic className="mr-1.5 h-4 w-4" /> Dicter
              </TabsTrigger>
              <TabsTrigger value="import">
                <Upload className="mr-1.5 h-4 w-4" /> Importer
              </TabsTrigger>
            </TabsList>

            <TabsContent value="text" className="space-y-3 pt-2">
              <Textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="Ex : Paul Martin a fait 8h du lundi au jeudi et 7h le vendredi (heures faites). Sophie Durand est prévue 7h tous les jours la semaine prochaine (heures prévues)."
                rows={6}
              />
              <div className="flex justify-end">
                <Button
                  type="button"
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
            </TabsContent>

            <TabsContent value="voice" className="space-y-3 pt-2">
              {dictation.isSupported ? (
                <>
                  <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed py-6">
                    <Button
                      type="button"
                      variant={dictation.isListening ? 'destructive' : 'default'}
                      size="lg"
                      onClick={() => (dictation.isListening ? dictation.stop() : dictation.start())}
                    >
                      {dictation.isListening ? (
                        <>
                          <MicOff className="mr-2 h-5 w-5" /> Arrêter la dictée
                        </>
                      ) : (
                        <>
                          <Mic className="mr-2 h-5 w-5" /> Démarrer la dictée
                        </>
                      )}
                    </Button>
                    <p className="text-xs text-muted-foreground">
                      {dictation.isListening
                        ? 'Parlez maintenant…'
                        : 'Le texte dicté apparaît ci-dessous, modifiable avant analyse.'}
                    </p>
                    {dictation.error && (
                      <p className="text-xs text-destructive">{dictation.error}</p>
                    )}
                  </div>
                  <Textarea
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    placeholder="La transcription apparaîtra ici…"
                    rows={4}
                  />
                  <div className="flex justify-end">
                    <Button
                      type="button"
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
                </>
              ) : (
                <div className="rounded-md border border-amber-200 bg-amber-50/70 p-4 text-sm text-amber-900">
                  La dictée vocale n'est pas supportée par ce navigateur. Utilisez Chrome ou
                  Edge, ou saisissez le texte dans l'onglet « Texte ».
                </div>
              )}
            </TabsContent>

            <TabsContent value="import" className="space-y-3 pt-2">
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
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
}

function errorMessage(error: unknown): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail ===
      'string'
  ) {
    return (error as { response: { data: { detail: string } } }).response.data.detail;
  }
  return "L'analyse a échoué. Réessayez.";
}
