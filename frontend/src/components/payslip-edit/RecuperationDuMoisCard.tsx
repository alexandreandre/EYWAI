import { useState } from 'react';
import { Loader2 } from 'lucide-react';

import {
  annulerPaiementRecuperation,
  choisirLeMoisRecuperation,
  payerSoldeRecuperation,
} from '@/api/modulation';
import { generatePayslip } from '@/api/payslips';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/components/ui/use-toast';
import { getPayrollGenerationErrorMessage, getUserErrorMessage } from '@/lib/errorMessages';
import {
  CONSEQUENCE_DU_CHOIX,
  heuresFr,
  lireRecuperation,
} from '@/features/payroll/utils/recuperationDuMois';
import { regenererPuisRecharger } from '@/features/payroll/utils/regenerationBulletin';

interface Props {
  payslipData: unknown;
  employeeId: string;
  year: number;
  month: number;
  contractPeriodId?: string | null;
  companyId?: string | null;
  /** Bulletin retouché à la main : un recalcul écraserait les retouches. */
  manuallyEdited: boolean;
  disabled?: boolean;
  onRegenerated: () => Promise<void> | void;
}

/**
 * Heures de récupération du mois (spec 2026-11-05) : ce qui est parti au
 * compteur, le choix de payer ce mois-ci, le paiement du solde. Chaque geste
 * recalcule le bulletin ; rien ne reste en attente sans le dire.
 */
export function RecuperationDuMoisCard({
  payslipData,
  employeeId,
  year,
  month,
  contractPeriodId,
  companyId,
  manuallyEdited,
  disabled,
  onRegenerated,
}: Props) {
  const { toast } = useToast();
  const [enCours, setEnCours] = useState(false);
  const etat = lireRecuperation(payslipData);
  if (!etat) return null;

  const agir = async (geste: () => Promise<void>, fait: string) => {
    setEnCours(true);
    try {
      try {
        await geste();
      } catch (erreur) {
        toast({
          title: 'Rien n’a été changé',
          description: getUserErrorMessage(erreur),
          variant: 'destructive',
        });
        return;
      }
      if (manuallyEdited) {
        toast({
          title: `${fait}.`,
          description:
            'Le bulletin a des retouches à la main : recalculez-le avec « Régénérer » ' +
            'pour appliquer ce choix (les retouches seront écrasées).',
        });
        return;
      }
      const issue = await regenererPuisRecharger(
        () =>
          generatePayslip(
            {
              employee_id: employeeId,
              year,
              month,
              ...(contractPeriodId ? { contract_period_id: contractPeriodId } : {}),
            },
            undefined,
            companyId,
          ),
        onRegenerated,
      );
      if (issue.kind === 'echec') {
        toast({
          title: `${fait}, mais le bulletin n’a pas été recalculé.`,
          description: `${getPayrollGenerationErrorMessage(issue.erreur)} Utilisez « Régénérer ».`,
          variant: 'destructive',
        });
        return;
      }
      toast({ title: `${fait}. Bulletin recalculé.` });
    } finally {
      setEnCours(false);
    }
  };

  const bloque = disabled || enCours;

  return (
    <Card data-testid="carte-recuperation">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Heures de récupération</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {etat.payeesCeMois ? (
          <div className="space-y-2">
            <p>
              Les {heuresFr(etat.heuresSupDuMois)} d’heures sup de ce mois sont payées sur ce
              bulletin, au lieu d’aller au compteur.
            </p>
            <Button
              size="sm"
              variant="outline"
              disabled={bloque}
              onClick={() =>
                agir(
                  () =>
                    choisirLeMoisRecuperation(
                      employeeId,
                      year,
                      month,
                      { payer: false, heures_sup: etat.heuresSupDuMois },
                      companyId,
                    ),
                  'Heures remises au compteur',
                )
              }
            >
              Remettre au compteur
            </Button>
          </div>
        ) : etat.heuresSupAuCompteur > 0 ? (
          <div className="space-y-2">
            <p>
              {heuresFr(etat.heuresSupAuCompteur)} d’heures sup mises au compteur ce mois-ci, soit{' '}
              {heuresFr(etat.reposCredite)} de repos.
              {etat.heuresSupDuMois > etat.heuresSupAuCompteur
                ? ` Les ${heuresFr(etat.heuresSupDuMois - etat.heuresSupAuCompteur)} au-delà du plafond sont payées.`
                : ''}
            </p>
            <Button
              size="sm"
              variant="outline"
              disabled={bloque}
              onClick={() =>
                agir(
                  () =>
                    choisirLeMoisRecuperation(
                      employeeId,
                      year,
                      month,
                      { payer: true, heures_sup: etat.heuresSupDuMois },
                      companyId,
                    ),
                  'Heures sup payées ce mois-ci',
                )
              }
            >
              Payer ces heures ce mois-ci
            </Button>
            <p className="text-xs text-muted-foreground">{CONSEQUENCE_DU_CHOIX}</p>
          </div>
        ) : etat.heuresSupDuMois > 0 ? (
          <p>
            Compteur au plafond : les {heuresFr(etat.heuresSupDuMois)} d’heures sup de ce mois sont
            payées.
          </p>
        ) : (
          <p>Aucune heure sup ce mois-ci.</p>
        )}

        <div className="space-y-2 border-t pt-3">
          <p>
            Solde du compteur à la fin du mois : <strong>{heuresFr(etat.solde)}</strong>
          </p>
          {etat.soldePaye > 0 ? (
            <div className="space-y-2">
              <p>{heuresFr(etat.soldePaye)} du compteur payées sur ce bulletin, en prime.</p>
              <Button
                size="sm"
                variant="outline"
                disabled={bloque}
                onClick={() =>
                  agir(
                    () => annulerPaiementRecuperation(employeeId, year, month, companyId),
                    'Paiement annulé, heures rendues au compteur',
                  )
                }
              >
                Annuler le paiement
              </Button>
            </div>
          ) : etat.solde > 0 ? (
            <div className="space-y-1">
              <Button
                size="sm"
                variant="outline"
                disabled={bloque}
                onClick={() =>
                  agir(
                    () =>
                      payerSoldeRecuperation(employeeId, year, month, etat.solde, companyId),
                    `Solde de ${heuresFr(etat.solde)} payé sur ce bulletin`,
                  )
                }
              >
                Payer le solde ({heuresFr(etat.solde)})
              </Button>
              <p className="text-xs text-muted-foreground">
                Payé en prime, au taux horaire de base : des heures mises en repos n’ont plus
                l’exonération ni les réductions des heures sup.
              </p>
            </div>
          ) : null}
        </div>
        {enCours ? (
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" /> Recalcul du bulletin…
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
