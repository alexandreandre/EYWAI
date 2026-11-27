import { useEffect, useState } from 'react';
import { Loader2, Trash2, Undo2 } from 'lucide-react';
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
import { ToastAction } from '@/components/ui/toast';
import { useToast } from '@/components/ui/use-toast';
import * as calendarApi from '@/api/calendar';
import { runWithConcurrency } from '@/lib/concurrency';
import { restoreCalendarSnapshots, type CalendarUndoSnapshot } from '@/lib/calendarBulkUndo';
import { calendarSaveFailureMessage } from '@/lib/calendarSaveFeedback';
import {
  messageDuVidage,
  phraseConfirmationVidage,
  type BilanVidage,
} from '@/lib/viderCalendrier';

export interface SalarieAVider {
  id: string;
  nom: string;
}

interface ViderCalendrierDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  salaries: SalarieAVider[];
  year: number;
  month: number;
  companyId?: string;
  /** Appelé après le vidage (ou son annulation) : recharger les calendriers. */
  onDone: () => void;
}

type Apercu =
  | { etat: 'lecture' }
  | { etat: 'pret'; bilan: BilanVidage; illisibles: string[] }
  | { etat: 'erreur'; message: string };

function moisEnLettres(year: number, month: number): string {
  return new Date(year, month - 1).toLocaleString('fr-FR', { month: 'long', year: 'numeric' });
}

function bilanDe(resultats: calendarApi.ViderMoisResultat[], moisLabel: string): BilanVidage {
  return {
    joursVides: resultats.reduce((n, r) => n + r.jours_vides.length, 0),
    joursAbsence: resultats.reduce((n, r) => n + r.jours_gardes_absence.length, 0),
    joursBulletin: resultats.reduce((n, r) => n + r.jours_gardes_bulletin.length, 0),
    salaries: resultats.filter((r) => r.jours_vides.length > 0).length,
    moisLabel,
  };
}

/**
 * « Vider le calendrier du mois » (retour d'Elsa : annuler un modèle appliqué
 * par erreur). L'aperçu du serveur dit d'abord combien de jours seront vidés et
 * combien restent (absences posées, bulletins validés) ; rien n'est écrit avant
 * la confirmation. Le message final propose « Annuler ».
 */
export function ViderCalendrierDialog({
  open,
  onOpenChange,
  salaries,
  year,
  month,
  companyId,
  onDone,
}: ViderCalendrierDialogProps) {
  const { toast } = useToast();
  const [apercu, setApercu] = useState<Apercu>({ etat: 'lecture' });
  const [enCours, setEnCours] = useState(false);
  const moisLabel = moisEnLettres(year, month);
  const cle = salaries.map((s) => s.id).join(',');

  useEffect(() => {
    if (!open) return;
    let annule = false;
    setApercu({ etat: 'lecture' });
    void (async () => {
      const illisibles: string[] = [];
      const resultats = await runWithConcurrency(
        salaries.map((s) => async () => {
          try {
            return await calendarApi.viderMoisDuCalendrier(s.id, year, month, { apercu: true }, { companyId });
          } catch {
            illisibles.push(s.nom);
            return null;
          }
        }),
        5,
      );
      if (annule) return;
      const lus = resultats.filter((r): r is calendarApi.ViderMoisResultat => r !== null);
      if (lus.length === 0) {
        setApercu({ etat: 'erreur', message: 'Les calendriers n’ont pas pu être lus : rien n’a été vidé. Réessayez.' });
        return;
      }
      setApercu({ etat: 'pret', bilan: bilanDe(lus, moisLabel), illisibles });
    })();
    return () => {
      annule = true;
    };
    // `cle` suit la liste des salariés.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, cle, year, month, companyId, moisLabel]);

  const annulerLeVidage = async (snapshots: CalendarUndoSnapshot[]) => {
    try {
      await restoreCalendarSnapshots(snapshots, year, month);
      toast({ title: 'Vidage annulé', description: 'Les calendriers ont retrouvé leur état d’avant.' });
    } catch (error) {
      toast({ title: 'Annulation non confirmée', description: calendarSaveFailureMessage(error), variant: 'destructive' });
    } finally {
      onDone();
    }
  };

  const vider = async () => {
    setEnCours(true);
    const snapshots: CalendarUndoSnapshot[] = [];
    const resultats: calendarApi.ViderMoisResultat[] = [];
    const echecs: string[] = [];
    await runWithConcurrency(
      salaries.map((s) => async () => {
        try {
          const avant = (await calendarApi.getCalendarSnapshot(s.id, year, month, { companyId })).data;
          const res = await calendarApi.viderMoisDuCalendrier(
            s.id,
            year,
            month,
            { apercu: false, expectedRevision: avant.revision },
            { companyId },
          );
          resultats.push(res);
          if (res.jours_vides.length > 0) {
            snapshots.push({
              id: s.id,
              companyId: companyId ?? '',
              expectedRevision: res.revision,
              planned: avant.calendrier_prevu,
              actual: avant.calendrier_reel,
            });
          }
        } catch (error) {
          echecs.push(`${s.nom} : ${calendarSaveFailureMessage(error)}`);
        }
      }),
      5,
    );
    setEnCours(false);
    onOpenChange(false);
    const bilan = bilanDe(resultats, moisLabel);
    if (resultats.length > 0) {
      toast({
        ...messageDuVidage(bilan),
        action:
          snapshots.length > 0 ? (
            <ToastAction altText="Annuler le vidage" onClick={() => void annulerLeVidage(snapshots)}>
              <Undo2 className="mr-1 h-3.5 w-3.5" />
              Annuler
            </ToastAction>
          ) : undefined,
      });
    }
    if (echecs.length > 0) {
      toast({
        title: echecs.length > 1 ? `${echecs.length} calendriers non vidés` : 'Calendrier non vidé',
        description: echecs.join(' — '),
        variant: 'destructive',
      });
    }
    onDone();
  };

  const titre =
    salaries.length === 1
      ? `Vider le calendrier de ${salaries[0].nom} — ${moisLabel}`
      : `Vider le calendrier de ${salaries.length} salariés — ${moisLabel}`;
  const rienAVider = apercu.etat === 'pret' && apercu.bilan.joursVides === 0;

  return (
    <AlertDialog open={open} onOpenChange={(o) => !enCours && onOpenChange(o)}>
      <AlertDialogContent data-testid="dialogue-vider-calendrier">
        <AlertDialogHeader>
          <AlertDialogTitle>{titre}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-2 text-sm text-muted-foreground">
              {apercu.etat === 'lecture' && (
                <p className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" /> Lecture des calendriers…
                </p>
              )}
              {apercu.etat === 'erreur' && <p className="text-destructive">{apercu.message}</p>}
              {apercu.etat === 'pret' && (
                <>
                  <p className="font-medium text-foreground" data-testid="bilan-vidage">
                    {phraseConfirmationVidage(apercu.bilan)}
                  </p>
                  {!rienAVider && (
                    <p>
                      Les jours vidés redeviennent « à saisir ». Arrêts, congés et absences se
                      retirent dans Congés ou Arrêts &amp; IJ.
                    </p>
                  )}
                  {apercu.illisibles.length > 0 && (
                    <p className="text-destructive">
                      Non lus, donc non vidés : {apercu.illisibles.join(', ')}.
                    </p>
                  )}
                </>
              )}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={enCours}>{rienAVider ? 'Fermer' : 'Annuler'}</AlertDialogCancel>
          {!rienAVider && (
            <Button
              variant="destructive"
              disabled={apercu.etat !== 'pret' || enCours}
              onClick={() => void vider()}
            >
              {enCours ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
              Vider
            </Button>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
