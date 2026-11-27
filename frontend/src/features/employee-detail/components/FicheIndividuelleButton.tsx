import { useState } from 'react';
import { FileSpreadsheet, Loader2 } from 'lucide-react';

import { telechargerFicheIndividuelle } from '@/api/exports';
import { residencePermitsExportErrorMessage as messageDuServeur } from '@/api/residencePermits';
import { Button } from '@/components/ui/button';
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
import {
  messagePeriode,
  periodeParDefaut,
  type PeriodeFiche,
} from '@/features/employee-detail/utils/ficheIndividuelle';

/**
 * « Fiche individuelle (Excel) » (lot L18, 27/11/2026) : les cumuls du salarié
 * mois par mois, lus sur ses bulletins Martine. Utile pour l'indemnité de départ.
 */
export function FicheIndividuelleButton({ employeeId }: { employeeId: string }) {
  const [ouverte, setOuverte] = useState(false);
  const [periode, setPeriode] = useState<PeriodeFiche>(() => periodeParDefaut());
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const refus = messagePeriode(periode);

  const telecharger = async () => {
    if (refus) return;
    setEnCours(true);
    setErreur(null);
    try {
      await telechargerFicheIndividuelle(employeeId, periode);
      setOuverte(false);
    } catch (e) {
      setErreur(await messageDuServeur(e, 'La fiche n’a pas pu être préparée. Réessayez dans un instant.'));
    } finally {
      setEnCours(false);
    }
  };

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="w-full sm:w-auto"
        onClick={() => {
          setErreur(null);
          setOuverte(true);
        }}
      >
        <FileSpreadsheet className="mr-2 h-4 w-4" aria-hidden />
        Fiche individuelle (Excel)
      </Button>
      <Dialog open={ouverte} onOpenChange={setOuverte}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Fiche individuelle</DialogTitle>
            <DialogDescription>
              Les cumuls du salarié mois par mois (brut, cotisations, net, impôt, heures) et son
              salaire de référence de l’indemnité de départ. Les mois sans bulletin Martine
              apparaissent vides, avec la mention « mois non payé dans Martine ».
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="fiche-debut">Premier mois</Label>
              <Input
                id="fiche-debut"
                type="month"
                value={periode.debut}
                onChange={(e) => setPeriode((p) => ({ ...p, debut: e.target.value }))}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="fiche-fin">Dernier mois</Label>
              <Input
                id="fiche-fin"
                type="month"
                value={periode.fin}
                onChange={(e) => setPeriode((p) => ({ ...p, fin: e.target.value }))}
              />
            </div>
          </div>
          {refus ? <p className="text-sm text-amber-700">{refus}</p> : null}
          {erreur ? (
            <p role="alert" className="text-sm text-destructive">
              {erreur}
            </p>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOuverte(false)}>
              Annuler
            </Button>
            <Button type="button" onClick={() => void telecharger()} disabled={Boolean(refus) || enCours}>
              {enCours ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
              Télécharger
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
