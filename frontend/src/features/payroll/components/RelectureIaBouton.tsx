import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Sparkles } from 'lucide-react';

import {
  getDroitsRelecture,
  getEtatRelecture,
  getPreparationRelecture,
  lancerRelecture,
  type PreparationRelecture,
  type RelectureIa,
  type SalarieARelire,
} from '@/api/relectureIa';
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
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import {
  coutAffiche,
  raisonBoutonGrise,
  selectionRelecture,
  texteProgression,
  type SelectionRelecture,
} from '@/features/payroll/utils/relectureIa';
import { toast } from '@/hooks/use-toast';
import { showErrorToast } from '@/lib/errorMessages';
import { pluriel } from '@/lib/pluriel';
import { queryKeys } from '@/lib/queryKeys';

type Props = { year: number; month: number; titreMois: string };

/** Bouton « Relire la paie avec l'IA », visible des seuls comptes autorisés. */
export function RelectureIaBouton(props: Props) {
  const droits = useQuery({
    queryKey: queryKeys.relectureIaDroits(),
    queryFn: getDroitsRelecture,
    staleTime: 5 * 60_000,
  });
  if (!droits.data?.peut_lancer) return null;
  return <BoutonAutorise {...props} />;
}

const INTERVALLE_SUIVI_MS = 2500;

function BoutonAutorise({ year, month, titreMois }: Props) {
  const queryClient = useQueryClient();
  const [confirmation, setConfirmation] = useState(false);

  const preparation = useQuery({
    queryKey: queryKeys.relectureIaPreparation(year, month),
    queryFn: () => getPreparationRelecture(year, month),
    staleTime: 30_000,
  });
  const etat = useQuery({
    queryKey: queryKeys.relectureIaEtat(),
    queryFn: getEtatRelecture,
    refetchInterval: (query) =>
      query.state.data?.relecture?.statut === 'en_cours' ? INTERVALLE_SUIVI_MS : false,
  });
  const relecture = etat.data?.relecture ?? null;
  const enCours = relecture?.statut === 'en_cours';

  // La fin se dit une fois, si la page a vu la relecture tourner.
  const statutVu = useRef<RelectureIa['statut'] | null>(null);
  useEffect(() => {
    const statut = relecture?.statut ?? null;
    if (statutVu.current === 'en_cours' && statut && statut !== 'en_cours') {
      toast({
        title: statut === 'terminee' ? 'Relecture terminée' : 'Relecture arrêtée',
        description: relecture?.message ?? undefined,
        variant: statut === 'terminee' ? 'default' : 'destructive',
      });
      void queryClient.invalidateQueries({ queryKey: queryKeys.relectureIaPreparation(year, month) });
      void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[2] === 'relecture-ia' });
    }
    statutVu.current = statut;
  }, [relecture?.statut, relecture?.message, queryClient, year, month]);

  const lancement = useMutation({
    mutationFn: ({ companyIds, employeeIds }: SelectionRelecture) =>
      lancerRelecture(year, month, companyIds, employeeIds),
    onSuccess: (resultat) => {
      setConfirmation(false);
      if (resultat.message) toast({ title: 'Relecture', description: resultat.message });
      void queryClient.invalidateQueries({ queryKey: queryKeys.relectureIaEtat() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.relectureIaPreparation(year, month) });
    },
    onError: (error) => {
      showErrorToast(error, {
        title: 'Relecture non lancée',
        fallback: 'La relecture n’a pas pu démarrer. Réessayez dans un instant.',
      });
    },
  });

  const raison = enCours ? null : raisonBoutonGrise(preparation.data);
  const grise = enCours || preparation.isLoading || preparation.isError || raison !== null;
  const messageDuMois =
    relecture && !enCours && relecture.year === year && relecture.month === month
      ? relecture.message
      : null;

  return (
    <div className="flex max-w-xs flex-col items-end gap-1" data-testid="relecture-ia">
      <Button
        className="gap-1.5"
        disabled={grise}
        onClick={() => setConfirmation(true)}
        data-testid="relecture-ia-bouton"
      >
        {enCours ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        ) : (
          <Sparkles className="h-3.5 w-3.5" aria-hidden />
        )}
        Relire la paie avec l’IA
      </Button>
      {enCours && relecture ? (
        <p className="text-right text-xs text-muted-foreground" data-testid="relecture-ia-progression">
          {texteProgression(relecture)} Vous pouvez quitter la page.
        </p>
      ) : null}
      {raison ? (
        <p className="text-right text-xs text-muted-foreground" data-testid="relecture-ia-raison">
          {raison}
        </p>
      ) : null}
      {preparation.isError ? (
        <p className="text-right text-xs text-destructive">
          La préparation de la relecture n’a pas pu être lue. Rechargez la page.
        </p>
      ) : null}
      {messageDuMois ? (
        <p
          className={
            relecture?.statut === 'echec'
              ? 'text-right text-xs text-destructive'
              : 'text-right text-xs text-muted-foreground'
          }
          data-testid="relecture-ia-fin"
        >
          {messageDuMois}
        </p>
      ) : null}
      {confirmation && preparation.data ? (
        <FenetreConfirmation
          preparation={preparation.data}
          titreMois={titreMois}
          envoi={lancement.isPending}
          onFermer={() => setConfirmation(false)}
          onLancer={(selection) => lancement.mutate(selection)}
        />
      ) : null}
    </div>
  );
}

/** Liste des salariés d'une société, tous cochés au départ. */
function ChoixDesSalaries({
  salaries,
  exclus,
  onBasculer,
}: {
  salaries: SalarieARelire[];
  exclus: ReadonlySet<string>;
  onBasculer: (ids: string[], exclure: boolean) => void;
}) {
  const [recherche, setRecherche] = useState('');
  const terme = recherche.trim().toLowerCase();
  const visibles = terme ? salaries.filter((p) => p.nom.toLowerCase().includes(terme)) : salaries;
  const ids = visibles.map((p) => p.employee_id);

  return (
    <div className="ml-6 mt-2 space-y-2 rounded-md border p-2" data-testid="relecture-ia-salaries">
      {salaries.length > 8 ? (
        <Input
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
          placeholder="Chercher un salarié"
          aria-label="Chercher un salarié"
          className="h-8"
        />
      ) : null}
      <div className="flex gap-3 text-xs">
        <button type="button" className="text-primary underline" onClick={() => onBasculer(ids, false)}>
          Tout cocher
        </button>
        <button type="button" className="text-primary underline" onClick={() => onBasculer(ids, true)}>
          Tout décocher
        </button>
      </div>
      <ul className="max-h-48 space-y-1 overflow-y-auto">
        {visibles.map((salarie) => (
          <li key={salarie.employee_id} className="flex items-center gap-2">
            <Checkbox
              id={`relecture-salarie-${salarie.employee_id}`}
              checked={!exclus.has(salarie.employee_id)}
              onCheckedChange={(valeur) => onBasculer([salarie.employee_id], valeur !== true)}
            />
            <label htmlFor={`relecture-salarie-${salarie.employee_id}`} className="flex-1 text-sm">
              {salarie.nom}
              {salarie.bulletins > 1 ? ` (${salarie.bulletins} bulletins)` : ''}
            </label>
          </li>
        ))}
        {visibles.length === 0 ? (
          <li className="text-xs text-muted-foreground">Aucun salarié à ce nom parmi ceux à relire.</li>
        ) : null}
      </ul>
    </div>
  );
}

function FenetreConfirmation({
  preparation,
  titreMois,
  envoi,
  onFermer,
  onLancer,
}: {
  preparation: PreparationRelecture;
  titreMois: string;
  envoi: boolean;
  onFermer: () => void;
  onLancer: (selection: SelectionRelecture) => void;
}) {
  const [decochees, setDecochees] = useState<ReadonlySet<string>>(new Set());
  const [exclus, setExclus] = useState<ReadonlySet<string>>(new Set());
  const [ouverte, setOuverte] = useState<string | null>(null);
  const selection = useMemo(
    () => selectionRelecture(preparation.societes, decochees, exclus),
    [preparation.societes, decochees, exclus],
  );
  const nombre = selection.nombre;

  const basculer = (companyId: string) => {
    setDecochees((avant) => {
      const apres = new Set(avant);
      if (!apres.delete(companyId)) apres.add(companyId);
      return apres;
    });
  };

  const basculerSalaries = (ids: string[], exclure: boolean) => {
    setExclus((avant) => {
      const apres = new Set(avant);
      ids.forEach((id) => (exclure ? apres.add(id) : apres.delete(id)));
      return apres;
    });
  };

  return (
    <AlertDialog open onOpenChange={(estOuverte) => !estOuverte && onFermer()}>
      <AlertDialogContent className="max-h-[90vh] overflow-y-auto">
        <AlertDialogHeader>
          <AlertDialogTitle>Êtes-vous sûre ?</AlertDialogTitle>
          <AlertDialogDescription>
            L’IA relit les bulletins de {titreMois.toLowerCase()} et dit quoi regarder. Elle ne
            modifie rien.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <ul className="space-y-2 text-sm" data-testid="relecture-ia-societes">
          {preparation.societes.map((societe) => {
            const cochee = !decochees.has(societe.company_id);
            const retires = societe.salaries.filter((p) => exclus.has(p.employee_id)).length;
            return (
              <li key={societe.company_id}>
                <div className="flex items-start gap-2">
                  <Checkbox
                    id={`relecture-${societe.company_id}`}
                    checked={cochee}
                    onCheckedChange={() => basculer(societe.company_id)}
                    className="mt-0.5"
                  />
                  <label htmlFor={`relecture-${societe.company_id}`} className="flex-1">
                    <span className="font-medium">{societe.nom}</span>
                    <span className="block text-xs text-muted-foreground">
                      {pluriel(societe.a_relire, 'bulletin')} à relire sur {societe.bulletins_generes}
                      {retires > 0 ? `, ${pluriel(retires, 'salarié retiré', 'salariés retirés')}` : ''}
                      {societe.sans_regles ? ', sans règle propre à cette société' : ''}
                    </span>
                  </label>
                  {cochee && societe.a_relire > 0 ? (
                    <button
                      type="button"
                      className="shrink-0 text-xs text-primary underline"
                      aria-expanded={ouverte === societe.company_id}
                      onClick={() =>
                        setOuverte(ouverte === societe.company_id ? null : societe.company_id)
                      }
                      data-testid="relecture-ia-choisir"
                    >
                      {ouverte === societe.company_id ? 'Fermer' : 'Choisir les salariés'}
                    </button>
                  ) : null}
                </div>
                {cochee && ouverte === societe.company_id ? (
                  <ChoixDesSalaries
                    salaries={societe.salaries}
                    exclus={exclus}
                    onBasculer={basculerSalaries}
                  />
                ) : null}
              </li>
            );
          })}
        </ul>

        <p className="text-sm" data-testid="relecture-ia-recap">
          {pluriel(nombre, 'bulletin')} à relire.
        </p>
        <p className="text-base font-semibold" data-testid="relecture-ia-prix">
          Prix de cette relecture : {coutAffiche(nombre * preparation.cout_unitaire_eur)}
        </p>
        <p className="text-sm" data-testid="relecture-ia-avertissement">
          À lancer une fois, quand la paie du mois est prête, et pas à répétition : chaque relecture a
          un coût.
        </p>
        <p className="text-xs text-muted-foreground">
          {preparation.derniere_relecture
            ? `Dernière relecture de ce mois : le ${new Date(preparation.derniere_relecture).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })}.`
            : 'Ce mois n’a jamais été relu.'}{' '}
          Seuls les bulletins modifiés depuis sont relus.
        </p>

        <AlertDialogFooter>
          <AlertDialogCancel>Annuler</AlertDialogCancel>
          <Button
            disabled={nombre === 0 || envoi}
            onClick={() => onLancer(selection)}
            data-testid="relecture-ia-lancer"
          >
            {envoi ? 'Lancement…' : 'Lancer la relecture'}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
