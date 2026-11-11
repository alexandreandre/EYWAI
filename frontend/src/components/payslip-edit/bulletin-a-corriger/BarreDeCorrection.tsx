/**
 * Barre fixe en bas : où qu'elle soit dans la page, la RH voit ce qui reste à
 * appliquer (le 12/09, des heures corrigées n'avaient jamais été enregistrées).
 * Après « Appliquer » : le net avant et après, et « Annuler ».
 */
import { Loader2, Undo2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { eurosFr } from '@/features/payroll/utils/correctionsBulletin';

interface Props {
  changements: number;
  /** Lignes ouvertes avec une valeur tapée et sans motif : rien n'y est en attente. */
  lignesSansMotif?: number;
  recalculPrevu: boolean;
  enCours: boolean;
  resultat: { netAvant: number | null; netApres: number | null } | null;
  onAppliquer: () => void;
  onToutAnnuler: () => void;
  onAnnulerLApplication: () => void;
  onFermerResultat: () => void;
}

const net = (valeur: number | null) => (valeur == null ? '—' : eurosFr(valeur));

function PhraseSansMotif({ nombre }: { nombre: number }) {
  if (nombre <= 0) return null;
  return (
    <p className="font-semibold text-amber-300" data-testid="lignes-sans-motif">
      {nombre === 1
        ? '1 ligne ouverte sans motif : choisissez son motif, sinon elle n’est pas appliquée.'
        : `${nombre} lignes ouvertes sans motif : choisissez leur motif, sinon elles ne sont pas appliquées.`}
    </p>
  );
}

export default function BarreDeCorrection(props: Props) {
  const { changements, recalculPrevu, enCours, resultat } = props;
  const sansMotif = props.lignesSansMotif ?? 0;
  if (changements === 0 && sansMotif === 0 && !resultat && !enCours) return null;
  return (
    <>
      <div className="h-24" aria-hidden="true" />
      <div className="fixed inset-x-0 bottom-0 z-[60] border-t bg-gray-900 text-white shadow-[0_-4px_16px_rgba(0,0,0,0.15)]">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          {enCours ? (
            <p className="flex items-center gap-2 text-sm" role="status" aria-live="polite">
              <Loader2 className="h-4 w-4 animate-spin" /> Martine recalcule le bulletin…
            </p>
          ) : changements > 0 ? (
            <>
              <div className="text-sm" data-testid="barre-enregistrement">
                <p className="font-semibold">
                  {changements} changement{changements > 1 ? 's' : ''} à appliquer
                </p>
                <p className="text-gray-300">
                  {recalculPrevu
                    ? 'Le bulletin sera recalculé en entier : brut, cotisations, net et cumuls.'
                    : 'Seules les notes changent : le bulletin n’est pas recalculé.'}
                </p>
                <PhraseSansMotif nombre={sansMotif} />
              </div>
              <div className="flex gap-2">
                <Button variant="outline" className="bg-white text-gray-900 hover:bg-gray-100" onClick={props.onToutAnnuler}>
                  <Undo2 className="mr-2 h-4 w-4" /> Tout annuler
                </Button>
                <Button className="bg-green-700 hover:bg-green-800" data-testid="enregistrer-barre" onClick={props.onAppliquer}>
                  Appliquer
                </Button>
              </div>
            </>
          ) : resultat ? (
            <>
              <div className="text-sm">
                <p data-testid="resultat-application" role="status" aria-live="polite">
                  Bulletin recalculé · Net : {net(resultat.netAvant)} →{' '}
                  <span className="font-bold text-green-300">{net(resultat.netApres)}</span>
                </p>
                <PhraseSansMotif nombre={sansMotif} />
              </div>
              <div className="flex gap-2">
                <Button variant="outline" className="bg-white text-gray-900 hover:bg-gray-100" data-testid="annuler-application" onClick={props.onAnnulerLApplication}>
                  <Undo2 className="mr-2 h-4 w-4" /> Annuler
                </Button>
                <Button variant="ghost" size="sm" aria-label="Fermer" onClick={props.onFermerResultat}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </>
          ) : sansMotif > 0 ? (
            <div className="text-sm" data-testid="barre-enregistrement">
              <p className="font-semibold">Rien à appliquer pour l’instant</p>
              <PhraseSansMotif nombre={sansMotif} />
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}
