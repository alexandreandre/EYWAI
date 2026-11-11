import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

const ETAPES = ['Cliquez sur la ligne fausse, ou « Ajouter une ligne »', 'Remplissez', 'Appliquez'];

export default function BandeauEtapes({ etape }: { etape: 1 | 2 | 3 }) {
  return (
    <ol className="grid gap-1.5 sm:grid-cols-3" data-testid="bandeau-etapes">
      {ETAPES.map((texte, i) => {
        const numero = i + 1;
        const etat = numero < etape ? 'faite' : numero === etape ? 'en-cours' : 'a-venir';
        return (
          <li
            key={texte}
            data-testid={`etape-${numero}`}
            data-etat={etat}
            className={cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-sm',
              etat === 'faite' && 'bg-green-100 text-green-800 dark:bg-green-950/40 dark:text-green-300',
              etat === 'en-cours' && 'bg-blue-700 font-semibold text-white',
              etat === 'a-venir' && 'bg-muted text-muted-foreground'
            )}
          >
            {etat === 'faite' ? <Check className="h-4 w-4" /> : <span>{numero}.</span>}
            {texte}
          </li>
        );
      })}
    </ol>
  );
}
