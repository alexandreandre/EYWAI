import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  CircleDashed,
  Loader2,
} from 'lucide-react';
import { ControleIndisponible } from '@/features/payroll/components/ControleIndisponible';
import {
  phraseListeControle,
  type ListeControleMois as Liste,
} from '@/features/payroll/utils/listeControleMois';
import { cn } from '@/lib/utils';

type Props = {
  titreMois: string;
  liste: Liste | null;
  chargement: boolean;
  preflightEnErreur?: boolean;
  onRetryPreflight?: () => void;
  isRetrying?: boolean;
};

export function ListeControleMois({
  titreMois,
  liste,
  chargement,
  preflightEnErreur = false,
  onRetryPreflight,
  isRetrying = false,
}: Props) {
  return (
    <section
      className="rounded-xl border border-border bg-card px-4 py-3"
      data-testid="liste-controle-mois"
      aria-labelledby="liste-controle-mois-titre"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id="liste-controle-mois-titre" className="text-sm font-semibold">
            Liste de contrôle — {titreMois}
          </h2>
          <p className="text-xs text-muted-foreground">
            {chargement || !liste ? 'Vérification en cours…' : phraseListeControle(liste)}
          </p>
        </div>
        <Link
          to="/payroll/manuel"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
        >
          <BookOpen className="h-3.5 w-3.5" aria-hidden />
          Manuel de la paie
        </Link>
      </div>

      {preflightEnErreur ? (
        <ControleIndisponible
          className="mt-3"
          titre="Calendriers et conflits arrêt/heures non vérifiés."
          description="La liste ne les coche pas : une lecture a échoué. Réessayez, ou confirmez-les vous-même."
          onRetry={onRetryPreflight}
          isRetrying={isRetrying}
        />
      ) : null}

      {chargement || !liste ? (
        <p className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Chargement de la liste de contrôle…
        </p>
      ) : (
        <>
          <ul className="mt-3 space-y-1.5">
            {liste.etapes.map((etape) => (
              <li
                key={etape.id}
                className={cn(
                  'flex items-start gap-2 rounded-lg border px-3 py-2',
                  etape.etat === 'fait'
                    ? 'border-success/30 bg-success/5'
                    : etape.etat === 'a_faire'
                      ? 'border-amber-300/70 bg-amber-50/80 dark:border-amber-500/30 dark:bg-amber-950/20'
                      : 'border-border bg-muted/20'
                )}
              >
                <span className="mt-0.5 shrink-0">
                  {etape.etat === 'fait' ? (
                    <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />
                  ) : etape.etat === 'a_faire' ? (
                    <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" aria-hidden />
                  ) : etape.etat === 'inconnu' ? (
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-hidden />
                  ) : (
                    <CircleDashed className="h-4 w-4 text-muted-foreground" aria-hidden />
                  )}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium leading-tight">{etape.libelle}</p>
                  <p className="text-xs text-muted-foreground">{etape.detail}</p>
                  {etape.etat === 'fait' ? (
                    <span className="sr-only">Fait</span>
                  ) : etape.etat === 'a_confirmer' ? (
                    <span className="sr-only">À confirmer par vous</span>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>

          {liste.actions.length > 0 ? (
            <div className="mt-3 border-t border-border pt-3">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Actions en attente
              </h3>
              <ol className="mt-2 space-y-2">
                {liste.actions.map((action, index) => (
                  <li key={action.id} className="text-sm">
                    <p>
                      <span className="font-medium">
                        {index + 1}. {action.quoi}
                      </span>
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Cliquez sur{' '}
                      <Link to={action.href} className="font-medium text-primary hover:underline">
                        {action.ouCliquer}
                      </Link>
                      . Ensuite : {action.ensuite}
                    </p>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
