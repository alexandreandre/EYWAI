import { useState } from 'react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { MOTIFS_PROPOSES } from '@/features/payroll/utils/bulletinACorriger';

interface Props {
  valeur: string;
  onValeur: (motif: string) => void;
  disabled?: boolean;
  testId?: string;
}

/** Le motif en un clic. Il est imprimé sur le bulletin : « Autre… » ouvre un champ libre. */
export default function MotifEnPuces({ valeur, onValeur, disabled, testId }: Props) {
  const [autre, setAutre] = useState(() => valeur !== '' && !MOTIFS_PROPOSES.includes(valeur));
  return (
    <div className="space-y-2" data-testid={testId}>
      <p className="text-xs text-muted-foreground">Pourquoi ? (imprimé sur le bulletin)</p>
      <div className="flex flex-wrap gap-1.5">
        {MOTIFS_PROPOSES.map((motif) => (
          <button
            key={motif}
            type="button"
            disabled={disabled}
            onClick={() => {
              setAutre(false);
              onValeur(motif);
            }}
            className={cn(
              'rounded-full border px-3 py-1 text-xs',
              !autre && valeur === motif ? 'border-primary bg-primary text-primary-foreground' : 'bg-background'
            )}
          >
            {motif}
          </button>
        ))}
        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            setAutre(true);
            onValeur('');
          }}
          className={cn(
            'rounded-full border px-3 py-1 text-xs',
            autre ? 'border-primary bg-primary text-primary-foreground' : 'bg-background'
          )}
        >
          Autre…
        </button>
      </div>
      {autre ? (
        <Input
          autoFocus
          maxLength={300}
          placeholder="Écrivez le motif"
          value={valeur}
          disabled={disabled}
          onChange={(e) => onValeur(e.target.value)}
        />
      ) : null}
    </div>
  );
}
