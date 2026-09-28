/**
 * Après la création d'un salarié : ce qui a été posé et ce qui reste à faire.
 *
 * Remplace l'ancienne alerte qui ne donnait que l'identifiant et le mot de
 * passe : on dit si le planning est posé (sans lui, la paie s'arrête sur
 * « calendrier incomplet »), ce qui manque encore à la fiche (sa paie reste
 * bloquée d'ici là) et comment le salarié se connecte.
 */
import { Link } from 'react-router-dom';
import { AlertTriangle, CalendarCheck, CheckCircle2, KeyRound } from 'lucide-react';
import type { NouveauSalarieCree } from '@/api/employees';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { moisEnClair } from '@/features/employees/utils/valeursEmbauche';

type Props = {
  salarie: NouveauSalarieCree | null;
  onClose: () => void;
  onOuvrirFiche: (id: string) => void;
};

export function NouveauSalarieRecap({ salarie, onClose, onOuvrirFiche }: Props) {
  if (!salarie) return null;
  const nom = `${salarie.first_name} ${salarie.last_name}`.trim();
  const aCompleter = salarie.a_completer ?? [];
  const planning = moisEnClair(salarie.planning_mois);
  const plans = salarie.planning_plans ?? [];
  const avertissements = salarie.warnings ?? [];

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg" data-testid="recap-nouveau-salarie">
        <DialogHeader>
          <DialogTitle>Fiche créée : {nom}</DialogTitle>
          <DialogDescription>Ce qui est prêt, et ce qui reste à faire avant sa première paie.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 text-sm">
          <section className="flex gap-3">
            <CalendarCheck
              className={`mt-0.5 h-5 w-5 shrink-0 ${planning ? 'text-green-600' : 'text-amber-600'}`}
              aria-hidden
            />
            {planning ? (
              <p>
                <span className="font-medium">Planning posé</span> de {planning}
                {plans.length > 0 ? <> (plan « {plans.join(' », « ')} »)</> : null}.
              </p>
            ) : (
              <p>
                <span className="font-medium">Aucun planning posé</span> : aucun plan de planning actif ne couvre
                ce salarié. Posez-le dans{' '}
                <Link to="/schedules" className="underline" onClick={onClose}>
                  Plannings
                </Link>{' '}
                avant de générer sa paie.
              </p>
            )}
          </section>

          <section className="flex gap-3">
            {aCompleter.length > 0 ? (
              <>
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" aria-hidden />
                <div>
                  <p className="font-medium">À compléter avant sa première paie :</p>
                  <ul className="mt-1 list-inside list-disc">
                    {aCompleter.map((champ) => (
                      <li key={champ}>{champ}</li>
                    ))}
                  </ul>
                  <p className="mt-1 text-muted-foreground">
                    Sa paie reste bloquée d&apos;ici là. Sur la fiche : « Compléter la fiche ».
                  </p>
                </div>
              </>
            ) : (
              <>
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-green-600" aria-hidden />
                <p>
                  <span className="font-medium">Fiche complète</span> : sa paie peut être générée.
                </p>
              </>
            )}
          </section>

          <section className="flex gap-3">
            <KeyRound className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
            <div>
              <p>
                Connexion à l&apos;application : identifiant <span className="font-mono">{salarie.username}</span>,
                mot de passe provisoire <span className="font-mono">{salarie.generated_password}</span> (aussi
                dans le PDF de la fiche, onglet Documents).
              </p>
              {salarie.acces_application === false && (
                <p className="mt-1 text-muted-foreground">
                  Sans e-mail, pas de mot de passe oublié ni de notification : ajoutez-le à la fiche quand vous
                  l&apos;aurez.
                </p>
              )}
            </div>
          </section>

          {avertissements.length > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-950">
              {avertissements.map((a) => (
                <p key={a}>{a}</p>
              ))}
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={onClose}>
            Fermer
          </Button>
          <Button onClick={() => onOuvrirFiche(salarie.id)}>Ouvrir la fiche</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
