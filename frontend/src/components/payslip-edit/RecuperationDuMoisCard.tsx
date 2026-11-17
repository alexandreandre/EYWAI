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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { getPayrollGenerationErrorMessage, getUserErrorMessage } from '@/lib/errorMessages';
import {
  CONDITIONS_DU_COMPTEUR,
  CONSEQUENCE_DU_CHOIX,
  heuresFr,
  jouerLeGeste,
  lireHeuresAPayer,
  lireRecuperation,
  saisieParDefaut,
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
 * compteur, le choix de payer ce mois-ci, le paiement du solde (en entier ou
 * en partie : « 3 h sur 5 », le reste demeure au compteur). Chaque geste
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
  // null : la RH n'a rien tapé, le champ montre le solde (il suit le recalcul).
  const [saisieHeures, setSaisieHeures] = useState<string | null>(null);
  const etat = lireRecuperation(payslipData);
  if (!etat) return null;

  const recalculer = async () => {
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
    if (issue.kind === 'echec') throw issue.erreur;
  };

  const agir = async (geste: () => Promise<unknown>, defaire: () => Promise<unknown>, fait: string) => {
    setEnCours(true);
    try {
      const issue = await jouerLeGeste(geste, recalculer, defaire, manuallyEdited);
      if (issue.kind === 'refuse') {
        toast({
          title: 'Rien n’a été changé',
          description: getUserErrorMessage(issue.erreur),
          variant: 'destructive',
        });
      } else if (issue.kind === 'sans_recalcul') {
        toast({
          title: `${fait}.`,
          description:
            'Le bulletin a des retouches à la main : recalculez-le avec « Régénérer » ' +
            'pour appliquer ce choix (les retouches seront écrasées).',
        });
      } else if (issue.kind === 'defait') {
        toast({
          title: 'Rien n’a été changé',
          description: `Le bulletin n’a pas pu être recalculé, le geste a été défait. ${getPayrollGenerationErrorMessage(issue.erreur)}`,
          variant: 'destructive',
        });
      } else if (issue.kind === 'non_defait') {
        toast({
          title: `${fait}, mais le bulletin n’a pas été recalculé.`,
          description: `${getPayrollGenerationErrorMessage(issue.erreur)} Utilisez « Régénérer ».`,
          variant: 'destructive',
        });
      } else {
        toast({ title: `${fait}. Bulletin recalculé.` });
      }
    } finally {
      setEnCours(false);
    }
  };

  const bloque = disabled || enCours;
  const saisie = saisieHeures ?? saisieParDefaut(etat.soldePayable);
  const aPayer = lireHeuresAPayer(saisie, etat.soldePayable);
  const toutLeSolde = aPayer.kind === 'ok' && aPayer.heures === Math.round(etat.soldePayable * 100) / 100;
  type Choix = 'payer' | 'compteur' | 'regle';
  const appliquerLeChoix = (choix: Choix) =>
    choisirLeMoisRecuperation(
      employeeId,
      year,
      month,
      { choix, heures_sup: etat.heuresSupDuMois },
      companyId,
    );
  // `inverse` : le choix en vigueur avant le geste, pour le défaire si le recalcul échoue.
  const choisir = (choix: Choix, inverse: Choix, fait: string) =>
    agir(() => appliquerLeChoix(choix), () => appliquerLeChoix(inverse), fait);

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
            <Button size="sm" variant="outline" disabled={bloque} onClick={() => choisir('regle', 'payer', 'Heures remises au compteur')}>
              Remettre au compteur
            </Button>
          </div>
        ) : etat.heuresSupAuCompteur > 0 ? (
          <div className="space-y-2">
            <p>
              {heuresFr(etat.heuresSupAuCompteur)} d’heures sup mises au compteur ce mois-ci, soit{' '}
              {heuresFr(etat.reposCredite)} de repos.
              {etat.heuresSupDuMois > etat.heuresSupAuCompteur
                ? ` Les ${heuresFr(etat.heuresSupDuMois - etat.heuresSupAuCompteur)} restantes sont payées.`
                : ''}
            </p>
            <Button
              size="sm"
              variant="outline"
              disabled={bloque}
              onClick={() =>
                etat.auCompteurCeMois
                  ? choisir('regle', 'compteur', 'Heures sup payées ce mois-ci')
                  : choisir('payer', 'regle', 'Heures sup payées ce mois-ci')
              }
            >
              Payer ces heures ce mois-ci
            </Button>
            <p className="text-xs text-muted-foreground">{CONSEQUENCE_DU_CHOIX}</p>
          </div>
        ) : etat.regle === 'payees' && etat.heuresSupDuMois > 0 ? (
          <div className="space-y-2">
            <p>{heuresFr(etat.heuresSupDuMois)} d’heures sup payées ce mois-ci.</p>
            <Button size="sm" variant="outline" disabled={bloque} onClick={() => choisir('compteur', 'regle', 'Heures mises au compteur')}>
              Mettre ces heures au compteur
            </Button>
            <p className="text-xs text-muted-foreground">
              {CONSEQUENCE_DU_CHOIX} {CONDITIONS_DU_COMPTEUR}
            </p>
          </div>
        ) : etat.regle === 'compteur' && etat.heuresSupDuMois > 0 ? (
          <p>
            Compteur au plafond : les {heuresFr(etat.heuresSupDuMois)} d’heures sup de ce mois sont
            payées.
          </p>
        ) : null}

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
                    () => payerSoldeRecuperation(employeeId, year, month, etat.soldePaye, companyId),
                    'Paiement annulé, heures rendues au compteur',
                  )
                }
              >
                Annuler le paiement
              </Button>
            </div>
          ) : etat.soldePayable > 0 ? (
            <div className="space-y-1">
              <div className="flex flex-wrap items-end gap-2">
                <div className="space-y-1">
                  <Label htmlFor="heures-recuperation-a-payer" className="text-xs">
                    Heures à payer (solde : {heuresFr(etat.soldePayable)})
                  </Label>
                  <Input
                    id="heures-recuperation-a-payer"
                    data-testid="heures-recuperation-a-payer"
                    inputMode="decimal"
                    className="h-8 w-24"
                    value={saisie}
                    disabled={bloque}
                    aria-invalid={aPayer.kind === 'erreur'}
                    onChange={(e) => setSaisieHeures(e.target.value)}
                  />
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={bloque || aPayer.kind === 'erreur'}
                  onClick={() => {
                    if (aPayer.kind !== 'ok') return;
                    const heures = aPayer.heures;
                    void agir(
                      () => payerSoldeRecuperation(employeeId, year, month, heures, companyId),
                      () => annulerPaiementRecuperation(employeeId, year, month, companyId),
                      toutLeSolde
                        ? `Solde de ${heuresFr(heures)} payé sur ce bulletin`
                        : `${heuresFr(heures)} sur ${heuresFr(etat.soldePayable)} payées sur ce bulletin, le reste demeure au compteur`,
                    ).then(() => setSaisieHeures(null));
                  }}
                >
                  {aPayer.kind === 'ok' && !toutLeSolde
                    ? `Payer ${heuresFr(aPayer.heures)} sur ${heuresFr(etat.soldePayable)}`
                    : `Payer le solde (${heuresFr(etat.soldePayable)})`}
                </Button>
              </div>
              {aPayer.kind === 'erreur' ? (
                <p className="text-xs text-destructive">{aPayer.message}</p>
              ) : null}
              <p className="text-xs text-muted-foreground">
                Payé en prime, au taux horaire de base : des heures mises en repos n’ont plus
                l’exonération ni les réductions des heures sup. Les heures non payées restent au
                compteur.
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
