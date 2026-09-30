import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';

import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { effacerHeuresDesJours } from '@/api/calendar';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { getPayrollGenerationErrorMessage } from '@/lib/errorMessages';
import { queryKeys } from '@/lib/queryKeys';
import {
  effacerLesJours,
  libelleDesJours,
  lienModifierAbsence,
  messageEchecEffacement,
  messageHeuresEffacees,
  natureDuConflit,
  prenomDe,
  textesDuChoix,
  type JourEnConflit,
} from '@/features/payroll/utils/heuresSurArret';

type Props = {
  employeeId: string;
  /** Nom complet du salarié, s'il est connu : sert au prénom des boutons. */
  employeeName?: string | null;
  jours: JourEnConflit[];
  /**
   * Appelé une fois les heures effacées : relance la génération du même bulletin.
   * Jamais appelé si l'effacement échoue.
   */
  onEffacees: () => Promise<void> | void;
  /** Appelé quand on quitte pour l'écran des absences. */
  onModifier?: () => void;
};

/**
 * Le choix proposé quand des heures sont saisies un jour d'arrêt : soit le salarié
 * n'a pas travaillé (on efface ces heures et on relance), soit il a travaillé (on
 * corrige l'arrêt). Aucun forçage : le calcul ne se fait pas tant que ce n'est pas réglé.
 */
export function ChoixHeuresSurArret({
  employeeId,
  employeeName,
  jours,
  onEffacees,
  onModifier,
}: Props) {
  const { toast } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const companyId = useActiveCompanyId();
  const [enCours, setEnCours] = useState(false);
  const [echec, setEchec] = useState<string | null>(null);

  const textes = textesDuChoix(natureDuConflit(jours), prenomDe(employeeName));

  const effacer = async () => {
    setEnCours(true);
    setEchec(null);
    const resultat = await effacerLesJours(jours, (annee, mois, liste) =>
      effacerHeuresDesJours(employeeId, annee, mois, liste)
    );
    // Le calendrier du salarié a pu changer, même si l'effacement n'est que partiel.
    if (resultat.effaces.length > 0) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.schedules(companyId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.planning(companyId) });
    }
    if ('erreur' in resultat) {
      setEchec(
        messageEchecEffacement(
          resultat.effaces,
          getPayrollGenerationErrorMessage(resultat.erreur)
        )
      );
      setEnCours(false);
      return;
    }
    toast({ title: messageHeuresEffacees(resultat.effaces) });
    try {
      await onEffacees();
    } finally {
      setEnCours(false);
    }
  };

  return (
    <div className="space-y-3 text-sm" data-testid="choix-heures-sur-arret">
      <ul className="list-disc space-y-0.5 pl-5">
        {[...jours]
          .sort((a, b) => a.annee - b.annee || a.mois - b.mois || a.jour - b.jour)
          .map((j) => (
            <li key={`${j.annee}-${j.mois}-${j.jour}`}>
              {libelleDesJours([j])} : {j.heures.toLocaleString('fr-FR')} h saisies
            </li>
          ))}
      </ul>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button
          type="button"
          disabled={enCours}
          data-testid="effacer-heures-arret"
          onClick={() => void effacer()}
        >
          {enCours ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {textes.effacer}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={enCours}
          data-testid="modifier-arret"
          onClick={() => {
            onModifier?.();
            navigate(lienModifierAbsence(employeeId));
          }}
        >
          {textes.modifier}
        </Button>
      </div>
      {echec && (
        <p role="alert" className="text-destructive" data-testid="echec-effacement">
          {echec}
        </p>
      )}
    </div>
  );
}
