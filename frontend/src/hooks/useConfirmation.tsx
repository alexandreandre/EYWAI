import { useCallback, useRef, useState, type ReactNode } from 'react';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';

import { reponseUnique } from './confirmation';

export interface DemandeDeConfirmation {
  titre: string;
  /** Ce qui va se passer ; les retours à la ligne sont gardés. */
  description?: ReactNode;
  /** Libellé du bouton qui confirme (« Confirmer » par défaut). */
  confirmer?: string;
  annuler?: string;
  /** Action irréversible : bouton rouge. */
  destructif?: boolean;
}

/**
 * Une confirmation dans une fenêtre de l'application, à la place de
 * `window.confirm` : la fenêtre native du navigateur ne se voit pas dans les
 * vidéos de formation et ne ressemble pas au reste de l'écran (tournage H.2 et
 * H.6, 20/10/2026). `demander` rend une promesse : vrai si la personne
 * confirme, faux si elle annule ou ferme la fenêtre. Rendre `fenetre` dans le
 * composant.
 */
export function useConfirmation(): {
  demander: (demande: DemandeDeConfirmation) => Promise<boolean>;
  fenetre: ReactNode;
} {
  const [demande, setDemande] = useState<DemandeDeConfirmation | null>(null);
  const repondreRef = useRef<((oui: boolean) => void) | null>(null);

  const demander = useCallback((nouvelle: DemandeDeConfirmation) => {
    // Une demande encore ouverte se ferme sur « non ».
    repondreRef.current?.(false);
    const { promesse, repondre } = reponseUnique();
    repondreRef.current = repondre;
    setDemande(nouvelle);
    return promesse;
  }, []);

  const repondre = useCallback((oui: boolean) => {
    repondreRef.current?.(oui);
    repondreRef.current = null;
    setDemande(null);
  }, []);

  const fenetre = (
    <AlertDialog
      open={demande !== null}
      onOpenChange={(ouverte) => {
        if (!ouverte) repondre(false);
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{demande?.titre}</AlertDialogTitle>
          {demande?.description ? (
            <AlertDialogDescription className="whitespace-pre-line">
              {demande.description}
            </AlertDialogDescription>
          ) : null}
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => repondre(false)}>
            {demande?.annuler ?? 'Annuler'}
          </AlertDialogCancel>
          <AlertDialogAction
            className={cn(demande?.destructif && buttonVariants({ variant: 'destructive' }))}
            onClick={() => repondre(true)}
          >
            {demande?.confirmer ?? 'Confirmer'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );

  return { demander, fenetre };
}
