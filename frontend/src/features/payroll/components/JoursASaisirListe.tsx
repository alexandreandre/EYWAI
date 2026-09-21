import { Link } from 'react-router-dom';

import { formatFr, libelleSemaines } from '@/features/payroll/lib/fenetreVariables';
import { libellePlages, regrouperParSemaine } from '@/features/payroll/lib/joursASaisir';
import type { RefusalDetails } from '@/features/payroll/utils/generationGuards';

interface Props {
  details: RefusalDetails;
  /** Lien « Compléter le planning » ; absent dans la génération groupée. */
  lienPlanning?: string;
}

/**
 * Ce qui manque pour générer, tel que le serveur l'a jugé : la fenêtre des
 * variables, les jours à saisir par semaine, et ceux qui attendront le mois
 * suivant. Rien n'est recalculé ici — on montre ce que le 422 a dit.
 */
export function JoursASaisirListe({ details, lienPlanning }: Props) {
  const semaines = regrouperParSemaine(details.joursManquants);
  return (
    <div className="space-y-2 text-sm">
      {details.fenetre && (
        <p className="text-muted-foreground">
          Fenêtre des variables : du {formatFr(details.fenetre.debut)} au{' '}
          {formatFr(details.fenetre.fin)}
          {details.fenetre.semaines.length > 0
            ? ` (${libelleSemaines(details.fenetre.semaines)})`
            : ''}
          .
        </p>
      )}
      {semaines.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5">
          {semaines.map((s) => (
            <li key={`${s.annee}-${s.semaine}`}>{s.libelle}</li>
          ))}
        </ul>
      )}
      {details.joursInformatifs.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Hors fenêtre, à saisir pour le mois suivant :{' '}
          {libellePlages(details.joursInformatifs)}.
        </p>
      )}
      {lienPlanning && semaines.length > 0 && (
        <Link to={lienPlanning} className="text-xs underline underline-offset-2">
          Compléter le planning
        </Link>
      )}
    </div>
  );
}
