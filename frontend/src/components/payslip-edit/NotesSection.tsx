// frontend/src/components/payslip-edit/NotesSection.tsx

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { FileText, MessageSquare, Edit3 } from 'lucide-react';
import { InternalNote } from '@/api/payslips';

interface NotesSectionProps {
  pdfNotes: string;
  internalNote: string;
  internalNotes: InternalNote[];
  changesSummary: string;
  onPdfNotesChange: (value: string) => void;
  onInternalNoteChange: (value: string) => void;
  onChangesSummaryChange: (value: string) => void;
}

export default function NotesSection({
  pdfNotes,
  internalNote,
  internalNotes,
  changesSummary,
  onPdfNotesChange,
  onInternalNoteChange,
  onChangesSummaryChange,
}: NotesSectionProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquare className="h-5 w-5" />
          Notes & Commentaires
        </CardTitle>
        <CardDescription>
          Ajoutez des notes et un résumé des modifications
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Résumé des modifications (REQUIS) */}
        <div className="space-y-2">
          <Label htmlFor="changes-summary" className="flex items-center gap-2">
            <Edit3 className="h-4 w-4" />
            Résumé des modifications <span className="text-red-500">*</span>
          </Label>
          <Input
            id="changes-summary"
            value={changesSummary}
            onChange={(e) => onChangesSummaryChange(e.target.value)}
            placeholder="Ex: Ajout prime exceptionnelle 150€"
            maxLength={500}
            required
          />
          <p className="text-xs text-muted-foreground">
            {changesSummary.length}/500 caractères - Ce résumé sera visible dans l'historique
          </p>
        </div>

        <Separator />

        {/* Notes PDF (visibles sur le bulletin) */}
        <div className="space-y-2">
          <Label htmlFor="pdf-notes" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Notes visibles sur le bulletin PDF
          </Label>
          <Textarea
            id="pdf-notes"
            value={pdfNotes}
            onChange={(e) => onPdfNotesChange(e.target.value)}
            placeholder="Ces notes apparaîtront sur le bulletin PDF..."
            rows={3}
            maxLength={2000}
          />
          <p className="text-xs text-muted-foreground">
            {pdfNotes.length}/2000 caractères - Ces notes seront visibles par l'employé
          </p>
        </div>

        <Separator />

        {/* Note interne (pour cette modification uniquement) */}
        <div className="space-y-2">
          <Label htmlFor="internal-note" className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            Note interne (non visible sur le PDF)
          </Label>
          <Textarea
            id="internal-note"
            value={internalNote}
            onChange={(e) => onInternalNoteChange(e.target.value)}
            placeholder="Ajoutez un commentaire interne pour expliquer cette modification..."
            rows={2}
            maxLength={1000}
          />
          <p className="text-xs text-muted-foreground">
            {internalNote.length}/1000 caractères - Cette note sera visible uniquement par les RH/Admin
          </p>
        </div>

        {/* Historique des notes internes */}
        {internalNotes.length > 0 && (
          <>
            <Separator />
            <div className="space-y-2">
              <Label>Notes internes précédentes</Label>
              <div className="space-y-3 max-h-64 overflow-y-auto">
                {internalNotes.map((note) => (
                  <div
                    key={note.id}
                    className="p-3 bg-muted rounded-lg text-sm space-y-1"
                  >
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span className="font-medium">{note.author_name}</span>
                      <span>
                        {new Date(note.timestamp).toLocaleString('fr-FR')}
                      </span>
                    </div>
                    <p className="text-foreground">{note.content}</p>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
