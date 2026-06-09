import { useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from '@/components/ui/use-toast';
import { transmitEmployeeDocument } from '@/api/documents';
import { cn } from '@/lib/utils';
import { FileText, Loader2, Upload } from 'lucide-react';

const MAX_BYTES = 10 * 1024 * 1024;

interface TransmitEmployeeDocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employeeId: string;
  employeeName: string;
  onSuccess: () => void;
}

export function TransmitEmployeeDocumentDialog({
  open,
  onOpenChange,
  employeeId,
  employeeName,
  onSuccess,
}: TransmitEmployeeDocumentDialogProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [documentLabel, setDocumentLabel] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sendImmediately, setSendImmediately] = useState(true);
  const [isDragging, setIsDragging] = useState(false);

  const resetForm = () => {
    setDocumentLabel('');
    setSelectedFile(null);
    setSendImmediately(true);
    setIsDragging(false);
  };

  const handleClose = (next: boolean) => {
    if (!next) resetForm();
    onOpenChange(next);
  };

  const validateFile = (file: File | undefined): string | null => {
    if (!file) return 'Veuillez sélectionner un fichier PDF.';
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      return 'Seuls les fichiers PDF sont acceptés.';
    }
    if (file.size > MAX_BYTES) {
      return 'Le fichier dépasse la taille maximale autorisée (10 Mo).';
    }
    return null;
  };

  const pickFile = (file: File | undefined) => {
    const err = validateFile(file);
    if (err) {
      toast({ title: 'Fichier invalide', description: err, variant: 'destructive' });
      return;
    }
    setSelectedFile(file!);
  };

  const transmitMut = useMutation({
    mutationFn: () =>
      transmitEmployeeDocument(employeeId, selectedFile!, documentLabel.trim(), sendImmediately),
    onSuccess: () => {
      onSuccess();
      handleClose(false);
      toast({
        title: sendImmediately ? 'Document transmis' : 'Document enregistré',
        description: sendImmediately
          ? 'Le collaborateur a été notifié.'
          : 'Le document est en brouillon. Utilisez « Envoyer » pour le transmettre.',
      });
    },
    onError: (error: unknown) => {
      const msg =
        error && typeof error === 'object' && 'response' in error
          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: 'Transmission impossible',
        description: typeof msg === 'string' ? msg : 'Impossible d’enregistrer le document.',
        variant: 'destructive',
      });
    },
  });

  const canSubmit =
    documentLabel.trim().length >= 2 && selectedFile !== null && !transmitMut.isPending;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Transmettre un document</DialogTitle>
          <DialogDescription>
            Déposez un PDF à partager avec {employeeName} dans son espace documents.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="transmit-doc-label">Intitulé du document</Label>
            <Input
              id="transmit-doc-label"
              value={documentLabel}
              onChange={(e) => setDocumentLabel(e.target.value)}
              placeholder="Ex. Attestation mutuelle 2026"
              maxLength={120}
            />
            <p className="text-xs text-muted-foreground">
              Ce libellé sera visible par le collaborateur et dans la notification.
            </p>
          </div>

          <div
            className={cn(
              'rounded-lg border-2 border-dashed p-4 transition-colors',
              isDragging ? 'border-primary bg-primary/5' : 'border-border bg-muted/20',
            )}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setIsDragging(false);
              pickFile(event.dataTransfer.files?.[0]);
            }}
          >
            <div className="flex flex-col items-center gap-2 text-center">
              {selectedFile ? (
                <>
                  <FileText className="h-8 w-8 text-primary" aria-hidden />
                  <p className="text-sm font-medium">{selectedFile.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} Mo
                  </p>
                </>
              ) : (
                <>
                  <Upload className="h-8 w-8 text-muted-foreground" aria-hidden />
                  <p className="text-sm text-muted-foreground">
                    Glissez un PDF ici ou sélectionnez un fichier (max. 10 Mo)
                  </p>
                </>
              )}
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(event) => pickFile(event.target.files?.[0])}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={transmitMut.isPending}
                onClick={() => inputRef.current?.click()}
              >
                {selectedFile ? 'Changer de fichier' : 'Choisir un PDF'}
              </Button>
            </div>
          </div>

          <div className="flex items-start gap-2">
            <Checkbox
              id="transmit-send-immediately"
              checked={sendImmediately}
              onCheckedChange={(checked) => setSendImmediately(checked === true)}
            />
            <div className="grid gap-1 leading-none">
              <Label htmlFor="transmit-send-immediately" className="cursor-pointer font-normal">
                Envoyer immédiatement au collaborateur
              </Label>
              <p className="text-xs text-muted-foreground">
                Sinon, le document reste en brouillon (invisible côté salarié).
              </p>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleClose(false)}>
            Annuler
          </Button>
          <Button
            type="button"
            disabled={!canSubmit}
            onClick={() => transmitMut.mutate()}
          >
            {transmitMut.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Envoi…
              </>
            ) : sendImmediately ? (
              'Transmettre'
            ) : (
              'Enregistrer'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
