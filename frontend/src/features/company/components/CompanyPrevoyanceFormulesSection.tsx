import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Pencil, PlusCircle, Trash2 } from 'lucide-react';
import { useState } from 'react';

import {
  CLE_FORMULES_PREVOYANCE,
  type CategoriePrevoyance,
  type FormulePrevoyance,
  prevoyanceFormulesApi,
} from '@/api/prevoyanceFormules';
import {
  AlertDialog,
  AlertDialogAction,
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  BASES_PREVOYANCE,
  type LigneSaisie,
  ligneVide,
  lignesDeLaSaisie,
  saisieDesLignes,
} from '@/features/company/lib/formulesPrevoyanceSaisie';
import {
  libelleCategorie,
  messageFichesAMettreAJour,
  messageFichesMisesAJour,
} from '@/features/employees/utils/formulesPrevoyance';
import { useToast } from '@/hooks/use-toast';

const CATEGORIES: CategoriePrevoyance[] = ['non_cadre', 'cadre', 'tous'];

type Edition = { id: string | null; libelle: string; categorie: CategoriePrevoyance; lignes: LigneSaisie[] };

function editionVide(): Edition {
  return { id: null, libelle: '', categorie: 'non_cadre', lignes: [ligneVide()] };
}

function editionDe(formule: FormulePrevoyance): Edition {
  return {
    id: formule.id,
    libelle: formule.libelle,
    categorie: formule.statut_categoriel,
    lignes: saisieDesLignes(formule.lignes),
  };
}

/**
 * Formules de prévoyance de la société (02/11/2026) : la RH les crée une fois,
 * puis les choisit sur la fiche du salarié, qui en copie les lignes.
 */
export function CompanyPrevoyanceFormulesSection({ canEdit }: { canEdit: boolean }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: formules = [], isLoading } = useQuery({
    queryKey: CLE_FORMULES_PREVOYANCE,
    queryFn: prevoyanceFormulesApi.lister,
  });
  const actives = formules.filter((f) => f.is_active);
  const [edition, setEdition] = useState<Edition | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [aRetirer, setARetirer] = useState<FormulePrevoyance | null>(null);
  const [aMettreAJour, setAMettreAJour] = useState<{ id: string; libelle: string; nombre: number } | null>(null);

  const rafraichir = () => queryClient.invalidateQueries({ queryKey: CLE_FORMULES_PREVOYANCE });
  const echec = (e: unknown) =>
    toast({
      variant: 'destructive',
      title: 'Enregistrement impossible',
      description: e instanceof Error ? e.message : 'Réessayez dans un instant.',
    });

  const enregistrer = useMutation({
    mutationFn: async (saisie: Edition) => {
      const { lignes, erreur: invalide } = lignesDeLaSaisie(saisie.lignes);
      if (saisie.libelle.trim().length < 2) throw new Error('Donnez un nom à la formule.');
      if (invalide) throw new Error(invalide);
      const donnees = { libelle: saisie.libelle.trim(), statut_categoriel: saisie.categorie, lignes };
      if (!saisie.id) {
        await prevoyanceFormulesApi.creer(donnees);
        return null;
      }
      const retour = await prevoyanceFormulesApi.modifier(saisie.id, donnees);
      return { id: saisie.id, libelle: donnees.libelle, nombre: retour.fiches_a_mettre_a_jour };
    },
    onSuccess: (resultat) => {
      setEdition(null);
      setErreur(null);
      setAMettreAJour(resultat && resultat.nombre > 0 ? resultat : null);
      toast({ title: 'Formule enregistrée' });
      void rafraichir();
    },
    onError: (e) => setErreur(e instanceof Error ? e.message : 'Enregistrement impossible.'),
  });

  const retirer = useMutation({
    mutationFn: (id: string) => prevoyanceFormulesApi.retirer(id),
    onSuccess: () => {
      toast({ title: 'Formule retirée', description: 'Les fiches gardent leurs lignes.' });
      void rafraichir();
    },
    onError: echec,
  });

  const appliquer = useMutation({
    mutationFn: (id: string) => prevoyanceFormulesApi.appliquer(id),
    onSuccess: ({ fiches_mises_a_jour }) => {
      setAMettreAJour(null);
      toast({ title: messageFichesMisesAJour(fiches_mises_a_jour) });
      void queryClient.invalidateQueries({ queryKey: ['employees'] });
    },
    onError: echec,
  });

  const changerLigne = (index: number, champ: keyof LigneSaisie, valeur: string) =>
    setEdition((e) =>
      e ? { ...e, lignes: e.lignes.map((l, i) => (i === index ? { ...l, [champ]: valeur } : l)) } : e,
    );

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Créez ici les formules de prévoyance de la société. Sur la fiche du salarié, il suffit ensuite
        de choisir la formule : ses lignes sont copiées sur la fiche.
      </p>

      {aMettreAJour ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:bg-amber-950/30">
          <span>
            « {aMettreAJour.libelle} » : {messageFichesAMettreAJour(aMettreAJour.nombre)}
          </span>
          <Button size="sm" onClick={() => appliquer.mutate(aMettreAJour.id)} disabled={appliquer.isPending}>
            {appliquer.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Mettre à jour ces fiches
          </Button>
        </div>
      ) : null}

      {isLoading ? (
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      ) : actives.length === 0 ? (
        <p className="text-sm">Aucune formule pour l’instant.</p>
      ) : (
        <ul className="divide-y rounded-md border">
          {actives.map((f) => (
            <li key={f.id} className="flex items-center justify-between gap-3 p-3">
              <div>
                <p className="font-medium">{f.libelle}</p>
                <p className="text-xs text-muted-foreground">
                  {libelleCategorie(f.statut_categoriel)} ·{' '}
                  {f.lignes.length === 1 ? '1 ligne' : `${f.lignes.length} lignes`}
                </p>
              </div>
              {canEdit ? (
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" title="Modifier" onClick={() => setEdition(editionDe(f))}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Retirer"
                    className="text-destructive hover:text-destructive"
                    onClick={() => setARetirer(f)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {canEdit ? (
        <Button variant="outline" size="sm" onClick={() => setEdition(editionVide())}>
          <PlusCircle className="mr-2 h-4 w-4" />
          Nouvelle formule
        </Button>
      ) : null}

      <AlertDialog open={aRetirer !== null} onOpenChange={(ouverte) => (ouverte ? null : setARetirer(null))}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Retirer « {aRetirer?.libelle} » ?</AlertDialogTitle>
            <AlertDialogDescription>
              Elle ne sera plus proposée sur les fiches. Les fiches qui l’ont gardent leurs lignes.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (aRetirer) retirer.mutate(aRetirer.id);
                setARetirer(null);
              }}
            >
              Retirer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={edition !== null} onOpenChange={(ouverte) => (ouverte ? null : setEdition(null))}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{edition?.id ? 'Modifier la formule' : 'Nouvelle formule de prévoyance'}</DialogTitle>
            <DialogDescription>
              Les taux se saisissent en %, comme sur le contrat de l’organisme.
            </DialogDescription>
          </DialogHeader>
          {edition ? (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="formule-libelle">Nom de la formule</Label>
                  <Input
                    id="formule-libelle"
                    value={edition.libelle}
                    onChange={(e) => setEdition({ ...edition, libelle: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Pour qui</Label>
                  <Select
                    value={edition.categorie}
                    onValueChange={(v) => setEdition({ ...edition, categorie: v as CategoriePrevoyance })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CATEGORIES.map((c) => (
                        <SelectItem key={c} value={c}>
                          {libelleCategorie(c)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {edition.lignes.map((ligne, index) => (
                <div key={index} className="space-y-2 rounded-md border p-3">
                  <div className="flex items-end gap-2">
                    <div className="flex-grow space-y-1">
                      <Label>Libellé de la ligne</Label>
                      <Input value={ligne.libelle} onChange={(e) => changerLigne(index, 'libelle', e.target.value)} />
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Supprimer la ligne"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setEdition({ ...edition, lignes: edition.lignes.filter((_, i) => i !== index) })}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    {(
                      [
                        ['salarial', 'Taux salarial (%)'],
                        ['patronal', 'Taux patronal (%)'],
                      ] as const
                    ).map(([champ, libelle]) => (
                      <div key={champ} className="space-y-1">
                        <Label>{libelle}</Label>
                        <Input
                          inputMode="decimal"
                          value={ligne[champ]}
                          onChange={(e) => changerLigne(index, champ, e.target.value)}
                        />
                      </div>
                    ))}
                    <div className="space-y-1">
                      <Label>Base</Label>
                      <Select value={ligne.base} onValueChange={(v) => changerLigne(index, 'base', v)}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {BASES_PREVOYANCE.map((b) => (
                            <SelectItem key={b.valeur} value={b.valeur}>
                              {b.libelle}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEdition({ ...edition, lignes: [...edition.lignes, ligneVide()] })}
              >
                <PlusCircle className="mr-2 h-4 w-4" />
                Ajouter une ligne
              </Button>
              {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEdition(null)}>
              Annuler
            </Button>
            <Button onClick={() => edition && enregistrer.mutate(edition)} disabled={enregistrer.isPending}>
              {enregistrer.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
