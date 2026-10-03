import { useEffect, useState, type FormEvent } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';

import {
  createNewContract,
  getNewContractPreview,
  type NewContractResult,
} from '@/api/contractPeriods';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { Employee } from '@/features/employee-detail/types';
import {
  avecDateDeFin,
  corpsDeLaRequete,
  dateAncienneteRetenue,
  erreurDuFormulaire,
  formulaireInitial,
  type FormulaireNouveauContrat,
} from '@/features/employee-detail/nouveauContrat';
import { extractDetail, getUserErrorMessage, sanitizeBackendMessage } from '@/lib/errorMessages';

function jjmmaaaa(iso: string | null | undefined): string {
  const [annee, mois, jour] = (iso ?? '').slice(0, 10).split('-');
  return annee && mois && jour ? `${jour}/${mois}/${annee}` : '';
}

/** Le message du serveur s'il est lisible (refus, état laissé), sinon un message clair. */
function messageDEchec(erreur: unknown): string {
  return (
    sanitizeBackendMessage(extractDetail(erreur)) ??
    getUserErrorMessage(erreur, 'Le nouveau contrat n’a pas été enregistré.')
  );
}

interface NouveauContratDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employeeId: string;
  onEnregistre: (resultat: NewContractResult<Employee>) => void;
}

export function NouveauContratDialog({
  open,
  onOpenChange,
  employeeId,
  onEnregistre,
}: NouveauContratDialogProps) {
  const apercu = useQuery({
    queryKey: ['new-contract-preview', employeeId],
    queryFn: () => getNewContractPreview(employeeId),
    enabled: open,
    staleTime: 0,
  });
  const [form, setForm] = useState<FormulaireNouveauContrat | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    if (open && apercu.data && form === null) setForm(formulaireInitial(apercu.data));
  }, [open, apercu.data, form]);

  const enregistrer = useMutation({
    mutationFn: () => createNewContract<Employee>(employeeId, corpsDeLaRequete(form!)),
    onSuccess: (resultat) => {
      onEnregistre(resultat);
      fermer(false);
    },
    onError: (e) => setErreur(messageDEchec(e)),
  });

  function fermer(suivant: boolean) {
    if (!suivant) {
      setForm(null);
      setErreur(null);
    }
    onOpenChange(suivant);
  }

  function changer<K extends keyof FormulaireNouveauContrat>(cle: K, valeur: FormulaireNouveauContrat[K]) {
    setErreur(null);
    setForm((f) => (f ? { ...f, [cle]: valeur } : f));
  }

  function soumettre(event: FormEvent) {
    event.preventDefault();
    if (!form || !apercu.data) return;
    const probleme = erreurDuFormulaire(form, apercu.data);
    if (probleme) {
      setErreur(probleme);
      return;
    }
    enregistrer.mutate();
  }

  const data = apercu.data;
  const precedent = data?.contrat_precedent;

  return (
    <Dialog open={open} onOpenChange={fermer}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau contrat</DialogTitle>
          <DialogDescription>
            {precedent
              ? `Contrat précédent : ${precedent.contract_type} du ${jjmmaaaa(precedent.date_debut)} au ${jjmmaaaa(precedent.date_fin)}. Il reste dans les contrats passés, avec son départ et ses bulletins.`
              : 'La fiche repart sur un nouveau contrat et redevient active.'}
          </DialogDescription>
        </DialogHeader>

        {apercu.isLoading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Lecture de la fiche…
          </p>
        ) : apercu.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {messageDEchec(apercu.error)}
          </p>
        ) : data && !data.possible ? (
          <p role="alert" className="text-sm text-destructive">
            {data.raison}
          </p>
        ) : data && form ? (
          <form id="nouveau-contrat" onSubmit={soumettre} className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="nc-debut">Date de début</Label>
              <Input
                id="nc-debut"
                type="date"
                min={data.premier_jour_possible ?? undefined}
                value={form.dateDebut}
                onChange={(e) => changer('dateDebut', e.target.value)}
              />
              {data.premier_jour_possible ? (
                <p className="text-xs text-muted-foreground">
                  Au plus tôt le {jjmmaaaa(data.premier_jour_possible)}.
                </p>
              ) : null}
            </div>
            <div className="space-y-1">
              <Label>Type de contrat</Label>
              <Select value={form.typeContrat} onValueChange={(v) => changer('typeContrat', v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {data.types.map((type) => (
                    <SelectItem key={type} value={type}>
                      {type}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {avecDateDeFin(form.typeContrat) ? (
              <div className="space-y-1">
                <Label htmlFor="nc-fin">
                  Date de fin{form.typeContrat === 'CDD' ? '' : ' (facultative)'}
                </Label>
                <Input
                  id="nc-fin"
                  type="date"
                  value={form.dateFin}
                  onChange={(e) => changer('dateFin', e.target.value)}
                />
              </div>
            ) : null}
            <div className="space-y-1">
              <Label htmlFor="nc-duree">Durée hebdomadaire (h)</Label>
              <Input
                id="nc-duree"
                inputMode="decimal"
                value={form.duree}
                onChange={(e) => changer('duree', e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="nc-salaire">Salaire de base mensuel (€)</Label>
              <Input
                id="nc-salaire"
                inputMode="decimal"
                value={form.salaire}
                onChange={(e) => changer('salaire', e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="nc-poste">Poste</Label>
              <Input
                id="nc-poste"
                value={form.poste}
                onChange={(e) => changer('poste', e.target.value)}
              />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="nc-anciennete"
                  checked={form.reprendreAnciennete}
                  onCheckedChange={(v) => changer('reprendreAnciennete', v === true)}
                />
                <Label htmlFor="nc-anciennete">Reprendre l’ancienneté des contrats précédents</Label>
              </div>
              <p className="text-xs text-muted-foreground">{dateAncienneteRetenue(form, data)}</p>
            </div>
          </form>
        ) : null}

        {erreur ? (
          <p role="alert" className="text-sm text-destructive">
            {erreur}
          </p>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => fermer(false)}>
            {data && !data.possible ? 'Fermer' : 'Annuler'}
          </Button>
          {data?.possible && form ? (
            <Button type="submit" form="nouveau-contrat" disabled={enregistrer.isPending}>
              {enregistrer.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Enregistrement…
                </>
              ) : (
                'Enregistrer le nouveau contrat'
              )}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
