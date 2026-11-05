import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Check, ChevronsUpDown } from 'lucide-react';
import { getPropositionPcsEse, getReferentielPcsEse } from '@/api/pcsEse';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import {
  MENTION_ECAP,
  doitPreRemplir,
  filtrerRubriques,
  libelleCode,
  texteChangement,
  type ChangementPcs,
} from '@/features/pcs-ese/pcsEse';

/** Lignes affichées à la fois : la recherche affine, la liste reste rapide. */
const LIGNES_AFFICHEES = 80;

type Props = {
  value: string;
  onChange: (code: string) => void;
  poste: string;
  statut: string;
  employeeId?: string;
  changement?: ChangementPcs | null;
  disabled?: boolean;
};

function useRetarde(valeur: string, delaiMs: number): string {
  const [retardee, setRetardee] = useState(valeur);
  useEffect(() => {
    const t = setTimeout(() => setRetardee(valeur), delaiMs);
    return () => clearTimeout(t);
  }, [valeur, delaiMs]);
  return retardee;
}

/**
 * Le code PCS-ESE choisi dans la liste officielle, avec la proposition de Martine :
 * pré-rempli quand elle est sûre (et la raison dite), sinon trois codes probables.
 */
export function PcsEseField({ value, onChange, poste, statut, employeeId, changement, disabled }: Props) {
  const [ouvert, setOuvert] = useState(false);
  const [recherche, setRecherche] = useState('');
  const { data: rubriques = [], isLoading } = useQuery({
    queryKey: ['pcs-ese-referentiel'],
    queryFn: getReferentielPcsEse,
    staleTime: Infinity,
  });
  const posteRetarde = useRetarde(poste.trim(), 400);
  const { data: proposition } = useQuery({
    queryKey: ['pcs-ese-proposition', posteRetarde, statut, employeeId ?? null],
    queryFn: () =>
      getPropositionPcsEse({
        poste: posteRetarde,
        statut,
        ...(employeeId ? { employee_id: employeeId } : {}),
      }),
    enabled: posteRetarde.length >= 2 && !!statut,
    staleTime: 60_000,
  });

  // Une proposition sûre ne remplit le champ qu'une fois : la RH garde la main.
  const dejaRempli = useRef<string | null>(null);
  useEffect(() => {
    if (!proposition?.code) return;
    const cle = `${proposition.code}|${posteRetarde}|${statut}`;
    if (dejaRempli.current === cle || !doitPreRemplir(value, proposition)) return;
    dejaRempli.current = cle;
    onChange(proposition.code);
  }, [proposition, value, onChange, posteRetarde, statut]);

  const lignes = useMemo(
    () => filtrerRubriques(rubriques, recherche).slice(0, LIGNES_AFFICHEES),
    [rubriques, recherche],
  );
  const horsListe = !!value && rubriques.length > 0 && !rubriques.some((r) => r.code === value);
  const codeVide = value.trim() === '' || value.trim() === '9999';
  const proposeParMartine = !!proposition?.sur && proposition.code === value && dejaRempli.current !== null;
  const changementTexte = texteChangement(changement, value);

  return (
    <div className="space-y-2">
      <Popover open={ouvert} onOpenChange={setOuvert}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={ouvert}
            aria-label="Code PCS-ESE"
            disabled={disabled || isLoading}
            className="w-full justify-between font-normal"
          >
            <span className="truncate text-left">
              {value ? libelleCode(rubriques, value) : 'Choisir un code PCS-ESE'}
            </span>
            <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[min(36rem,90vw)] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput
              placeholder="Code, intitulé ou métier (ex. soudeur)…"
              value={recherche}
              onValueChange={setRecherche}
            />
            <CommandList>
              <CommandEmpty>Aucun code ne correspond.</CommandEmpty>
              {lignes.map(({ rubrique, metier }) => (
                <CommandItem
                  key={rubrique.code}
                  value={rubrique.code}
                  onSelect={() => {
                    onChange(rubrique.code);
                    setOuvert(false);
                    setRecherche('');
                  }}
                >
                  <Check className={cn('mr-2 h-4 w-4 shrink-0', value === rubrique.code ? 'opacity-100' : 'opacity-0')} />
                  <span className="flex flex-col">
                    <span>
                      <span className="font-medium">{rubrique.code}</span> — {rubrique.libelle}
                    </span>
                    {metier ? <span className="text-xs text-muted-foreground">Métier : {metier}</span> : null}
                    {rubrique.ecap ? <span className="text-xs text-muted-foreground">{MENTION_ECAP}</span> : null}
                  </span>
                </CommandItem>
              ))}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {horsListe ? (
        <p className="text-xs text-destructive">
          « {value} » n'est pas dans la liste officielle (table DSN PCSESE) : choisissez un code.
        </p>
      ) : null}

      {proposeParMartine ? (
        <p className="text-xs text-muted-foreground">
          Proposé par Martine : {proposition?.raison}
          {proposition?.ecap ? ` ${MENTION_ECAP}` : ''} Vous pouvez le changer.
        </p>
      ) : null}

      {!proposition?.sur && codeVide && proposition?.candidats.length ? (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">{proposition.raison} Codes probables :</p>
          <div className="flex flex-col gap-1">
            {proposition.candidats.map((c) => (
              <Button
                key={c.code}
                type="button"
                variant="outline"
                size="sm"
                className="h-auto justify-start whitespace-normal py-1 text-left font-normal"
                onClick={() => onChange(c.code)}
              >
                <span className="flex flex-col">
                  <span>
                    <span className="font-medium">{c.code}</span> — {c.libelle}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {c.raison}
                    {c.ecap && !c.raison.includes('ECAP') ? ` ${MENTION_ECAP}` : ''}
                  </span>
                </span>
              </Button>
            ))}
          </div>
        </div>
      ) : null}

      {!proposition?.sur && codeVide && proposition && !proposition.candidats.length ? (
        <p className="text-xs text-muted-foreground">{proposition.raison}</p>
      ) : null}

      {changementTexte ? <p className="text-xs text-muted-foreground">{changementTexte}</p> : null}
    </div>
  );
}
