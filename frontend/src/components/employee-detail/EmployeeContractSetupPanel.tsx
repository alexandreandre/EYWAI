import { useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { FileText, Loader2, Sparkles, Upload } from 'lucide-react';

interface EmployeeContractSetupPanelProps {
  onUpload: (file: File) => void;
  onGenerate: () => void;
  isUploading?: boolean;
  missingFields?: string[];
}

export function EmployeeContractSetupPanel({
  onUpload,
  onGenerate,
  isUploading = false,
  missingFields = [],
}: EmployeeContractSetupPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) return;
    onUpload(file);
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4 px-2 py-6">
      <div className="text-center">
        <p className="text-sm font-medium text-foreground">Aucun contrat pour ce collaborateur</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Déposez le contrat signé ou générez-le à partir des informations de la fiche.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
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
            handleFile(event.dataTransfer.files?.[0]);
          }}
        >
          <div className="flex h-full flex-col">
            <div className="mb-3 flex items-center gap-2">
              <Upload className="h-4 w-4 text-primary" aria-hidden />
              <p className="font-medium">Déposer le contrat signé</p>
            </div>
            <p className="mb-4 flex-1 text-sm text-muted-foreground">
              Importez le PDF signé (contrat externe ou version déjà validée).
            </p>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,application/pdf"
              className="hidden"
              onChange={(event) => handleFile(event.target.files?.[0])}
            />
            <Button
              type="button"
              variant="outline"
              className="w-full"
              disabled={isUploading}
              onClick={() => inputRef.current?.click()}
            >
              {isUploading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Enregistrement…
                </>
              ) : (
                <>
                  <FileText className="mr-2 h-4 w-4" />
                  Choisir un PDF
                </>
              )}
            </Button>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-4">
          <div className="mb-3 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" aria-hidden />
            <p className="font-medium">Générer un contrat</p>
          </div>
          <p className="mb-4 text-sm text-muted-foreground">
            Crée un contrat PDF à partir des données déjà renseignées sur la fiche collaborateur.
          </p>
          {missingFields.length > 0 ? (
            <p className="mb-4 text-xs text-amber-800">
              Informations recommandées avant génération : {missingFields.join(', ')}.
            </p>
          ) : null}
          <Button type="button" className="w-full" onClick={onGenerate}>
            <Sparkles className="mr-2 h-4 w-4" />
            Générer le contrat
          </Button>
        </div>
      </div>
    </div>
  );
}
