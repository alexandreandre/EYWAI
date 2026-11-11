/** Une prime ou une saisie du mois : son montant se change, elle se retire et se remet. */
import { useState } from 'react';
import { PencilLine, Trash2, Undo2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { pastilleSoumise } from '@/components/saisies/libellesSaisie';
import {
  type EtatCorrections,
  eurosFr,
  montantCorrigeDeLaPrime,
  type PrimeDuBulletin,
} from '@/features/payroll/utils/correctionsBulletin';
import { lireNombre } from '@/lib/nombreSaisi';
import { cn } from '@/lib/utils';

interface Props {
  prime: PrimeDuBulletin;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
}

function pastille(prime: PrimeDuBulletin): string {
  if (prime.surLeNet === 'retenue') return 'Retenue sur le net';
  if (prime.surLeNet === 'versement') return 'Versement sur le net';
  return pastilleSoumise(prime.soumise);
}

export default function LigneDePrime({ prime, etat, onChange, disabled }: Props) {
  const id = prime.saisieId;
  const retiree = etat.primesRetirees.includes(id);
  const initiale = prime.surLeNet === 'retenue' ? Math.abs(prime.montant) : prime.montant;
  const [ouverte, setOuverte] = useState(false);
  const [texte, setTexte] = useState(String(initiale).replace('.', ','));
  const [invalide, setInvalide] = useState(false);
  const affiche = prime.surLeNet === 'retenue' ? Math.abs(prime.montant) : prime.montant;

  return (
    <div
      data-testid={`prime-${id}`}
      className={cn(
        'flex flex-col gap-2 border-b px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between',
        retiree && 'bg-red-50 dark:bg-red-950/20'
      )}
    >
      <div className="min-w-0 flex-1">
        <span className={cn('font-medium', retiree && 'text-muted-foreground line-through')}>{prime.libelle}</span>
        <span className="ml-2 text-xs text-muted-foreground">{pastille(prime)}</span>
        {retiree ? (
          <span className="ml-2 rounded bg-red-100 px-1.5 text-xs font-semibold text-red-700 dark:bg-red-950/60 dark:text-red-300">
            Retirée
          </span>
        ) : null}
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        {ouverte && !retiree ? (
          <>
            <Input
              autoFocus
              data-testid={`montant-prime-${id}`}
              aria-label={`Montant de ${prime.libelle}`}
              inputMode="decimal"
              className="w-28 border-2 border-blue-500 text-right font-semibold"
              value={texte}
              onChange={(e) => {
                setTexte(e.target.value);
                const lu = lireNombre(e.target.value);
                setInvalide(lu === null);
                if (lu === null) return;
                const montant = montantCorrigeDeLaPrime(prime, lu);
                onChange({ ...etat, primes: etat.primes.map((p) => (p.saisieId === id ? { ...p, montant } : p)) });
              }}
            />
            <span>€</span>
            <Button variant="outline" size="sm" onClick={() => setOuverte(false)}>
              OK
            </Button>
            {invalide ? <p className="basis-full text-xs text-destructive">Tapez un montant, par exemple 150,50.</p> : null}
          </>
        ) : (
          <span className={cn('tabular-nums', retiree && 'text-muted-foreground line-through')}>{eurosFr(affiche)}</span>
        )}
        {disabled ? null : retiree ? (
          <Button
            variant="outline"
            size="sm"
            data-testid={`remettre-prime-${id}`}
            onClick={() => onChange({ ...etat, primesRetirees: etat.primesRetirees.filter((x) => x !== id) })}
          >
            <Undo2 className="mr-1 h-4 w-4" /> Remettre
          </Button>
        ) : (
          <>
            {!ouverte ? (
              <Button variant="outline" size="sm" aria-label={`Corriger ${prime.libelle}`} onClick={() => {
                  setTexte(String(initiale).replace('.', ','));
                  setInvalide(false);
                  setOuverte(true);
                }}
              >
                <PencilLine className="h-4 w-4" />
              </Button>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              className="text-red-700 dark:text-red-400"
              data-testid={`retirer-prime-${id}`}
              aria-label={`Retirer ${prime.libelle}`}
              onClick={() => {
                setOuverte(false);
                onChange({
                  ...etat,
                  primesRetirees: etat.primesRetirees.includes(id) ? etat.primesRetirees : [...etat.primesRetirees, id],
                });
              }}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
