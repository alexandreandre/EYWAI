import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { detectTimesheetColumns } from '@/api/calendar';

const ROLES = [
  { key: 'matricule', label: 'Matricule' },
  { key: 'last_name', label: 'Nom' },
  { key: 'first_name', label: 'Prénom' },
  { key: 'date', label: 'Date' },
  { key: 'hours', label: 'Heures' },
] as const;

interface TimesheetImportMappingDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  file: File | null;
  mapping: Record<string, string>;
  onConfirm: (mapping: Record<string, string>) => void;
}

export function TimesheetImportMappingDialog({
  open,
  onOpenChange,
  file,
  mapping,
  onConfirm,
}: TimesheetImportMappingDialogProps) {
  const [headers, setHeaders] = useState<string[]>([]);
  const [localMapping, setLocalMapping] = useState<Record<string, string>>(mapping);
  const [sampleRows, setSampleRows] = useState<Record<string, string | null>[]>([]);

  useEffect(() => {
    if (!open || !file) return;
    detectTimesheetColumns(file).then((res) => {
      setHeaders(res.headers);
      setSampleRows(res.sample_rows);
      setLocalMapping({ ...res.suggested_mapping, ...mapping });
    });
  }, [open, file, mapping]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Mapping des colonnes</DialogTitle>
          <DialogDescription>
            Associez les colonnes du fichier aux champs attendus par l&apos;import.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {ROLES.map(({ key, label }) => (
            <div key={key} className="grid grid-cols-2 items-center gap-2">
              <Label>{label}</Label>
              <Select
                value={localMapping[key] ?? '__none__'}
                onValueChange={(v) =>
                  setLocalMapping((prev) => ({
                    ...prev,
                    ...(v === '__none__' ? (() => {
                      const next = { ...prev };
                      delete next[key];
                      return next;
                    })() : { [key]: v }),
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="—" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">—</SelectItem>
                  {headers.map((h) => (
                    <SelectItem key={h} value={h}>
                      {h}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ))}
          {sampleRows.length > 0 && (
            <pre className="max-h-32 overflow-auto rounded-md bg-muted p-2 text-xs">
              {JSON.stringify(sampleRows[0], null, 2)}
            </pre>
          )}
          <Button
            type="button"
            className="w-full"
            onClick={() => {
              onConfirm(localMapping);
              onOpenChange(false);
            }}
          >
            Valider le mapping
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
