import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import * as absencesApi from '@/api/absences';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface EvenementFamilialBalanceDialogProps {
  triggerLabel?: string;
}

export function EvenementFamilialBalanceDialog({
  triggerLabel = 'Voir',
}: EvenementFamilialBalanceDialogProps) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<absencesApi.EvenementFamilialEvent[]>([]);
  const [loading, setLoading] = useState(false);

  const handleOpen = (next: boolean) => {
    setOpen(next);
    if (!next) return;
    setLoading(true);
    absencesApi
      .getEvenementsFamiliaux()
      .then((res) => setEvents(res.data.events ?? []))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  };

  return (
    <>
      <Button
        type="button"
        variant="link"
        className="h-auto p-0 text-xl font-bold text-primary"
        onClick={() => handleOpen(true)}
      >
        {triggerLabel}
      </Button>
      <Dialog open={open} onOpenChange={handleOpen}>
        <DialogContent className="flex max-h-[85vh] max-w-md flex-col overflow-hidden">
          <DialogHeader className="shrink-0">
            <DialogTitle>Événements familiaux – Jours restants</DialogTitle>
          </DialogHeader>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : events.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">
              Aucun événement familial disponible. Assurez-vous que votre
              convention collective est configurée.
            </p>
          ) : (
            <ul className="space-y-3 overflow-y-auto pr-1 text-sm">
              {events.map((ev) => (
                <li
                  key={ev.code}
                  className="flex items-start justify-between gap-2 border-b pb-2 last:border-0"
                >
                  <span className="font-medium">{ev.libelle}</span>
                  <span className="shrink-0 text-muted-foreground">
                    {ev.solde_restant} j restant
                    {ev.quota > 0 ? ` / ${ev.quota}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
