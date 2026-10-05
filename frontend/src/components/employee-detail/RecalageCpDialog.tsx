import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { AlertCircle, Loader2 } from 'lucide-react';

import { recalerSoldesCp, type CpRecalageResponse } from '@/api/leaveSettings';
import { Alert, AlertDescription } from '@/components/ui/alert';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { getUserErrorMessage } from '@/lib/errorMessages';

import { erreursRecalageCp, lireJours, moisDeRecalage } from './recalageCp';

interface RecalageCpDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employeeId: string;
  onRecale: (reponse: CpRecalageResponse) => void;
}

/**
 * Recaler les CP N-1 et N tels qu'ils doivent figurer en pied de bulletin à la
 * fin d'un mois écoulé. Les deux soldes sont saisis : celui qui ne change pas
 * aussi, car le mois choisi n'est pas aujourd'hui (le tableau, lui, montre le
 * solde du jour, acquisition du mois en cours comprise).
 */
export function RecalageCpDialog({ open, onOpenChange, employeeId, onRecale }: RecalageCpDialogProps) {
  const mois = useMemo(() => moisDeRecalage(new Date()), []);
  const [moisChoisi, setMoisChoisi] = useState(mois[0].valeur);
  const [n1, setN1] = useState('');
  const [n, setN] = useState('');
  const [note, setNote] = useState('');
  const [tente, setTente] = useState(false);

  const choisi = mois.find((m) => m.valeur === moisChoisi) ?? mois[0];
  const erreurs = erreursRecalageCp({ n1, n, note });

  const recalage = useMutation({
    mutationFn: () =>
      recalerSoldesCp(employeeId, {
        year: choisi.year,
        month: choisi.month,
        cp_n1_solde: lireJours(n1) ?? 0,
        cp_n_solde: lireJours(n) ?? 0,
        note: note.trim(),
      }),
    onSuccess: (reponse) => onRecale(reponse),
  });
  const { reset } = recalage;

  useEffect(() => {
    if (!open) return;
    setMoisChoisi(mois[0].valeur);
    setN1('');
    setN('');
    setNote('');
    setTente(false);
    reset();
  }, [open, mois, reset]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setTente(true);
    if (erreurs.length > 0 || recalage.isPending) return;
    recalage.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Recaler les congés payés</DialogTitle>
            <DialogDescription>
              Saisissez les soldes CP N-1 et N tels qu’ils doivent figurer en pied
              de bulletin à la fin du mois choisi (ancienneté et fractionnement
              compris). Les mois suivants partiront de ces soldes.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="recalage-cp-mois">Soldes à la fin de</Label>
            <Select value={moisChoisi} onValueChange={setMoisChoisi}>
              <SelectTrigger id="recalage-cp-mois">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {mois.map((m) => (
                  <SelectItem key={m.valeur} value={m.valeur}>
                    {m.libelle}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Soldes au {choisi.dateFin}, congés pris jusqu’à cette date déduits.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="recalage-cp-n1">CP N-1 (j)</Label>
              <Input
                id="recalage-cp-n1"
                inputMode="decimal"
                value={n1}
                onChange={(event) => setN1(event.target.value)}
                className="text-right tabular-nums"
                placeholder="ex. 12,5"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="recalage-cp-n">CP N (j)</Label>
              <Input
                id="recalage-cp-n"
                inputMode="decimal"
                value={n}
                onChange={(event) => setN(event.target.value)}
                className="text-right tabular-nums"
                placeholder="ex. 6,24"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="recalage-cp-note">Commentaire (obligatoire)</Label>
            <Textarea
              id="recalage-cp-note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Ex. un jour d’écart avec le bulletin Quadra de septembre"
              rows={3}
            />
          </div>

          {tente && erreurs.length > 0 ? (
            <ul className="space-y-1 text-sm text-destructive">
              {erreurs.map((erreur) => (
                <li key={erreur}>{erreur}</li>
              ))}
            </ul>
          ) : null}

          {recalage.isError ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {getUserErrorMessage(
                  recalage.error,
                  'Les soldes n’ont pas été enregistrés. Vérifiez la saisie et réessayez.',
                )}
              </AlertDescription>
            </Alert>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" disabled={recalage.isPending}>
              {recalage.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
              ) : null}
              Enregistrer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
