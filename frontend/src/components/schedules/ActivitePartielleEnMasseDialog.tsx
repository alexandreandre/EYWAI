import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Calendar } from '@/components/ui/calendar';
import { useToast } from '@/components/ui/use-toast';
import {
  apercuActivitePartielleEnMasse,
  poserActivitePartielleEnMasse,
  type DecompteEnMasse,
} from '@/api/activitePartielleEnMasse';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { displayNameNomPrenom } from '@/lib/employeeName';
import { estSaisissableLeMois } from '@/lib/employmentStatus';
import { apiErrorDetail } from '@/lib/badgeuseApiUtils';
import {
  JOURS_DE_LA_SEMAINE,
  NOMS_DES_JOURS,
  dateCourte,
  datesRetenues,
  erreurDePeriode,
  isoDuJourLocal,
  jourLocalDeIso,
  moisDesDates,
} from '@/lib/joursEnMasse';
import { detailDuSalarie, lignesDesRaisons, phraseDuDecompte } from '@/lib/decompteEnMasse';
import { pluriel } from '@/lib/pluriel';
import { invaliderApresSaisie } from '@/features/payroll/utils/invalidationsBulletin';

export interface SalarieDuChoix {
  id: string;
  first_name: string;
  last_name: string;
  nom_usage?: string | null;
  employment_status?: string | null;
  exit_last_working_day?: string | null;
  hire_date?: string | null;
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Tous les salariés de la société ; la fenêtre garde ceux saisissables sur les mois choisis. */
  employees: SalarieDuChoix[];
  employeesLoading: boolean;
  employeesError: boolean;
  /** Mois de la page : sert tant qu'aucun jour n'est choisi. */
  year: number;
  month: number;
  onApplied: () => void;
}

/** Délai avant de demander l'aperçu, le temps de finir de cocher. */
const DELAI_APERCU_MS = 400;

function Section({ titre, children }: { titre: string; children: ReactNode }) {
  return (
    <section className="space-y-2 rounded-md border p-3">
      <h3 className="text-sm font-semibold">{titre}</h3>
      {children}
    </section>
  );
}

function Decompte({ d }: { d: DecompteEnMasse }) {
  const lignes = lignesDesRaisons(d);
  const erreurs = d.salaries.filter((s) => s.erreurs.length > 0);
  return (
    <div className="space-y-2 text-sm" data-testid="ap-masse-decompte">
      <p className="font-medium">{phraseDuDecompte(d)}</p>
      {lignes.length > 0 && (
        <div>
          <p className="text-muted-foreground">
            {d.enregistre ? 'Jours laissés tels quels :' : 'Jours qui resteront tels quels :'}
          </p>
          <ul className="ml-5 list-disc">
            {lignes.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </div>
      )}
      {erreurs.length > 0 && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-destructive">
          {erreurs.map((s) => (
            <p key={s.employee_id}>
              {s.nom} : {s.erreurs.join(' ; ')}
            </p>
          ))}
        </div>
      )}
      {d.avertissement && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-amber-950">{d.avertissement}</p>
      )}
      {d.salaries.length > 0 && (
        <details>
          <summary className="cursor-pointer text-muted-foreground">Voir le détail par salarié</summary>
          <ul className="mt-1 max-h-48 space-y-1 overflow-y-auto">
            {d.salaries.map((s) => (
              <li key={s.employee_id}>
                <span className="font-medium">{s.nom}</span> : {detailDuSalarie(s, d)}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export function ActivitePartielleEnMasseDialog({
  open,
  onOpenChange,
  employees,
  employeesLoading,
  employeesError,
  year,
  month,
  onApplied,
}: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const companyId = useActiveCompanyId();
  const [du, setDu] = useState('');
  const [au, setAu] = useState('');
  const [joursSemaine, setJoursSemaine] = useState<number[]>([]);
  const [datesCliquees, setDatesCliquees] = useState<string[]>([]);
  // Les décochés plutôt que les cochés : un salarié qui apparaît en changeant
  // de mois est coché par défaut, comme les autres.
  const [decoches, setDecoches] = useState<Set<string>>(new Set());
  const [resultat, setResultat] = useState<DecompteEnMasse | null>(null);

  useEffect(() => {
    if (!open) return;
    setDu('');
    setAu('');
    setJoursSemaine([]);
    setDatesCliquees([]);
    setDecoches(new Set());
    setResultat(null);
  }, [open]);

  const dates = useMemo(
    () => datesRetenues({ du, au, joursSemaine, datesCliquees }),
    [du, au, joursSemaine, datesCliquees],
  );
  const periodeErreur = erreurDePeriode(du, au);

  // Salariés saisissables sur au moins un des mois choisis (le mois de la page sinon).
  const salaries = useMemo(() => {
    const mois = dates.length > 0 ? moisDesDates(dates) : [{ year, month }];
    return employees
      .filter((e) => mois.some((m) => estSaisissableLeMois(e, m.year, m.month)))
      .sort((a, b) => displayNameNomPrenom(a).localeCompare(displayNameNomPrenom(b), 'fr'));
  }, [employees, dates, year, month]);
  const coches = useMemo(() => salaries.filter((e) => !decoches.has(e.id)).map((e) => e.id), [salaries, decoches]);

  const demande = useMemo(() => ({ employee_ids: coches, dates }), [coches, dates]);
  const cleDemande = JSON.stringify(demande);
  const [cleStable, setCleStable] = useState(cleDemande);
  useEffect(() => {
    const t = window.setTimeout(() => setCleStable(cleDemande), DELAI_APERCU_MS);
    return () => window.clearTimeout(t);
  }, [cleDemande]);
  const pret = dates.length > 0 && coches.length > 0;
  const aJour = cleStable === cleDemande;

  const apercu = useQuery({
    queryKey: ['activite-partielle-en-masse-apercu', companyId, cleStable],
    queryFn: () => apercuActivitePartielleEnMasse(JSON.parse(cleStable) as typeof demande),
    enabled: open && pret && aJour && resultat === null,
    retry: false,
    staleTime: 0,
    gcTime: 0,
  });

  const enregistrement = useMutation({
    mutationFn: () => poserActivitePartielleEnMasse(demande),
    onSuccess: (d) => {
      setResultat(d);
      toast({
        title: d.total_passes > 0 ? 'Activité partielle enregistrée' : 'Rien n’a été posé',
        description: phraseDuDecompte(d),
        variant: d.salaries.some((s) => s.erreurs.length > 0) ? 'destructive' : undefined,
      });
      // Le serveur a marqué les bulletins touchés « à recalculer » : la paie le montre tout de suite.
      void invaliderApresSaisie(queryClient, companyId);
      void queryClient.invalidateQueries({ queryKey: ['activite-partielle-mois'] });
      onApplied();
    },
  });

  // Une erreur d'enregistrement vaut pour la demande qui l'a eue : un nouveau
  // choix rend l'aperçu.
  const { reset: oublierErreur } = enregistrement;
  useEffect(() => {
    oublierErreur();
  }, [cleDemande, oublierErreur]);

  const basculerJour = (indice: number, coche: boolean) =>
    setJoursSemaine((prev) => (coche ? [...new Set([...prev, indice])] : prev.filter((j) => j !== indice)));

  const basculerSalarie = (id: string, coche: boolean) =>
    setDecoches((prev) => {
      const next = new Set(prev);
      if (coche) next.delete(id);
      else next.add(id);
      return next;
    });

  const apercuCourant = aJour && apercu.data ? apercu.data : null;
  const peutEnregistrer =
    pret && apercuCourant !== null && apercuCourant.total_passes > 0 && !enregistrement.isPending && resultat === null;

  let blocApercu: ReactNode;
  if (resultat) {
    blocApercu = <Decompte d={resultat} />;
  } else if (enregistrement.isError) {
    blocApercu = (
      <p className="text-sm text-destructive">
        {apiErrorDetail(enregistrement.error, 'L’enregistrement a échoué. Rien n’est confirmé : rouvrez les calendriers pour vérifier.')}
      </p>
    );
  } else if (dates.length === 0) {
    blocApercu = (
      <p className="text-sm text-muted-foreground">
        Choisissez des jours : l’aperçu dira combien passeront en activité partielle.
      </p>
    );
  } else if (employeesLoading || employeesError) {
    blocApercu = (
      <p className="text-sm text-muted-foreground">
        {employeesLoading
          ? 'L’aperçu viendra une fois les salariés chargés.'
          : 'Sans la liste des salariés, l’aperçu ne peut pas être calculé.'}
      </p>
    );
  } else if (coches.length === 0) {
    blocApercu = <p className="text-sm text-muted-foreground">Cochez au moins un salarié pour voir l’aperçu.</p>;
  } else if (!aJour || apercu.isFetching) {
    blocApercu = (
      <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
        <Loader2 className="h-4 w-4 animate-spin" /> Calcul de l’aperçu…
      </p>
    );
  } else if (apercu.isError) {
    blocApercu = (
      <div className="space-y-2 text-sm text-destructive">
        <p>{apiErrorDetail(apercu.error, 'L’aperçu n’a pas pu être calculé.')}</p>
        <Button type="button" size="sm" variant="outline" onClick={() => void apercu.refetch()}>
          Réessayer
        </Button>
      </div>
    );
  } else if (apercuCourant) {
    blocApercu = <Decompte d={apercuCourant} />;
  } else {
    blocApercu = (
      <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
        <Loader2 className="h-4 w-4 animate-spin" /> Calcul de l’aperçu…
      </p>
    );
  }

  const moisAffiche = jourLocalDeIso(du || dates[0] || `${year}-${String(month).padStart(2, '0')}-01`);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Activité partielle en masse</DialogTitle>
          <DialogDescription>
            Choisissez les jours et les salariés. Les jours d’arrêt, de congé, de repos, les mois au bulletin
            validé et les jours hors contrat ne sont jamais touchés. Rien n’est enregistré avant « Enregistrer ».
          </DialogDescription>
        </DialogHeader>

        <fieldset disabled={resultat !== null || enregistrement.isPending} className="space-y-3">
          <Section titre="1. Les jours">
            <div className="flex flex-wrap items-end gap-3">
              <div className="space-y-1">
                <Label htmlFor="ap-masse-du">Du</Label>
                <Input id="ap-masse-du" type="date" value={du} onChange={(e) => setDu(e.target.value)} className="h-9 w-40" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="ap-masse-au">Au</Label>
                <Input id="ap-masse-au" type="date" value={au} onChange={(e) => setAu(e.target.value)} className="h-9 w-40" />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3" role="group" aria-label="Jours de la semaine">
              {JOURS_DE_LA_SEMAINE.map((court, i) => (
                <label key={court} className="flex items-center gap-1.5 text-sm">
                  <Checkbox
                    aria-label={NOMS_DES_JOURS[i]}
                    checked={joursSemaine.includes(i)}
                    onCheckedChange={(v) => basculerJour(i, v === true)}
                  />
                  {court}
                </label>
              ))}
            </div>
            {periodeErreur && <p className="text-xs text-destructive">{periodeErreur}</p>}
            {!periodeErreur && du && au && joursSemaine.length === 0 && (
              <p className="text-xs text-muted-foreground">Cochez les jours de la semaine à prendre sur cette période.</p>
            )}
            <details>
              <summary className="cursor-pointer text-sm text-muted-foreground">
                Ajouter ou retirer des dates une à une ({pluriel(datesCliquees.length, 'date cliquée', 'dates cliquées')})
              </summary>
              <Calendar
                mode="multiple"
                defaultMonth={moisAffiche}
                selected={datesCliquees.map(jourLocalDeIso)}
                onSelect={(choisies) => setDatesCliquees((choisies ?? []).map(isoDuJourLocal).sort())}
                weekStartsOn={1}
              />
            </details>
            <div data-testid="ap-masse-dates">
              {dates.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Aucun jour retenu : indiquez une période et cochez des jours de la semaine, ou cliquez des dates.
                </p>
              ) : (
                <p className="text-sm">
                  <span className="font-medium">{pluriel(dates.length, 'jour retenu', 'jours retenus')} :</span>{' '}
                  {dates.map(dateCourte).join(', ')}
                </p>
              )}
            </div>
          </Section>

          <Section titre="2. Les salariés">
            {employeesLoading ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                <Loader2 className="h-4 w-4 animate-spin" /> Chargement des salariés…
              </p>
            ) : employeesError ? (
              <p className="text-sm text-destructive">La liste des salariés n’a pas pu être chargée. Fermez et rouvrez la fenêtre.</p>
            ) : salaries.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun salarié en poste sur les mois choisis.</p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <span data-testid="ap-masse-nb-salaries">
                    {pluriel(coches.length, 'salarié coché', 'salariés cochés')} sur {salaries.length}
                  </span>
                  <Button type="button" variant="link" size="sm" className="h-auto p-0" onClick={() => setDecoches(new Set())}>
                    Tout cocher
                  </Button>
                  <Button
                    type="button"
                    variant="link"
                    size="sm"
                    className="h-auto p-0"
                    onClick={() => setDecoches(new Set(salaries.map((e) => e.id)))}
                  >
                    Tout décocher
                  </Button>
                </div>
                <ul className="grid max-h-48 grid-cols-1 gap-1 overflow-y-auto sm:grid-cols-2">
                  {salaries.map((e) => (
                    <li key={e.id}>
                      <label className="flex items-center gap-2 text-sm">
                        <Checkbox checked={!decoches.has(e.id)} onCheckedChange={(v) => basculerSalarie(e.id, v === true)} />
                        {displayNameNomPrenom(e)}
                      </label>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Section>
        </fieldset>

        <Section titre={resultat ? '3. Ce qui a été fait' : '3. Aperçu avant d’enregistrer'}>{blocApercu}</Section>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={enregistrement.isPending}>
            Fermer
          </Button>
          {resultat === null && (
            <Button type="button" onClick={() => enregistrement.mutate()} disabled={!peutEnregistrer}>
              {enregistrement.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {enregistrement.isPending
                ? 'Enregistrement…'
                : apercuCourant && apercuCourant.total_passes > 0
                  ? `Enregistrer ${pluriel(apercuCourant.total_passes, 'jour')}`
                  : 'Enregistrer'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
