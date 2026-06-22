import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Loader2, Trash2, Upload } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { revokeDsnPeriodImport } from '@/api/dsnImport';
import { useToast } from '@/hooks/use-toast';
import { getUserErrorMessage } from '@/lib/errorMessages';

const MONTH_FULL = [
  'Janvier',
  'Février',
  'Mars',
  'Avril',
  'Mai',
  'Juin',
  'Juillet',
  'Août',
  'Septembre',
  'Octobre',
  'Novembre',
  'Décembre',
];

function formatPeriodLabel(period: string): string {
  const [y, m] = period.split('-');
  const mi = parseInt(m, 10);
  if (!y || !mi || mi < 1 || mi > 12) return period;
  return `${MONTH_FULL[mi - 1]} ${y}`;
}

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companyId: string;
  companyName?: string | null;
  period: string;
  onReimport: () => void;
  onRevoked: () => void;
};

export function DsnPeriodActionDialog({
  open,
  onOpenChange,
  companyId,
  companyName,
  period,
  onReimport,
  onRevoked,
}: Props) {
  const { toast } = useToast();
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const revokeMutation = useMutation({
    mutationFn: () => revokeDsnPeriodImport(companyId, period),
    onSuccess: (data) => {
      toast({
        title: 'Import supprimé',
        description: `${formatPeriodLabel(period)} — ${data.cumuls_deleted} fichier(s) de cumuls retiré(s). Les fiches salariés sont conservées.`,
      });
      setConfirmDeleteOpen(false);
      onOpenChange(false);
      onRevoked();
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erreur',
        description: getUserErrorMessage(error, "Impossible de supprimer l'import."),
        variant: 'destructive',
      });
    },
  });

  const periodLabel = formatPeriodLabel(period);

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{periodLabel}</DialogTitle>
            <DialogDescription>
              DSN importée
              {companyName ? ` pour ${companyName}` : ''}. Choisissez une action.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col gap-2 sm:flex-col sm:space-x-0">
            <Button
              type="button"
              className="w-full justify-start gap-2"
              onClick={() => {
                onOpenChange(false);
                onReimport();
              }}
            >
              <Upload className="h-4 w-4" />
              Réimporter une DSN
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full justify-start gap-2 text-destructive hover:text-destructive"
              onClick={() => setConfirmDeleteOpen(true)}
            >
              <Trash2 className="h-4 w-4" />
              Supprimer l&apos;import
            </Button>
            <Button type="button" variant="ghost" className="w-full" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer l&apos;import de {periodLabel} ?</AlertDialogTitle>
            <AlertDialogDescription>
              Les cumuls du mois seront retirés et la case repassera en « manquant ». Les fiches
              salariés ne seront pas supprimées — comme lors d&apos;un réimport sans fichier.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={revokeMutation.isPending}>Annuler</AlertDialogCancel>
            <Button
              variant="destructive"
              disabled={revokeMutation.isPending}
              onClick={() => revokeMutation.mutate()}
            >
              {revokeMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Supprimer
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
