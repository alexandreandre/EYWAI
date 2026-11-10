/**
 * Les lignes du bulletin, chacune avec ses gestes (page client du 10/11, C1).
 *
 * « Au clic sur Modifier, toutes les lignes deviennent modifiables » : sur
 * l'onglet « Bulletin », chaque ligne propose « Corriger » (ce mois, carte
 * « Corriger une ligne ») et « Régulariser un mois passé » (carte des
 * régularisations de cotisation ou d'heures, avec la période). Le clic ouvre
 * l'onglet « Corriger » sur la bonne carte, pré-remplie. Rien ne se retouche
 * ici : toute correction reste une variable du mois, recalculée par Martine.
 */
import { useQuery } from '@tanstack/react-query';
import { History, PencilLine } from 'lucide-react';
import { useState } from 'react';

import { getLignesCorrigeables, type LigneCorrigeable } from '@/api/payslips';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  type DemandeDeCorrection,
  eurosFr,
  gestesDeLaLigne,
} from '@/features/payroll/utils/correctionsBulletin';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';

const BLOCS: Array<{ bloc: LigneCorrigeable['bloc']; titre: string }> = [
  { bloc: 'brut', titre: 'Rémunération' },
  { bloc: 'cotisations', titre: 'Cotisations' },
  { bloc: 'impot', titre: 'Impôt' },
];

function montantDe(ligne: LigneCorrigeable): string {
  if (ligne.bloc === 'cotisations') {
    const parts = [
      ligne.montant_salarial ? `salarial ${eurosFr(ligne.montant_salarial)}` : null,
      ligne.montant_patronal ? `patronal ${eurosFr(ligne.montant_patronal)}` : null,
    ].filter(Boolean);
    return parts.join(', ');
  }
  return ligne.montant != null ? eurosFr(ligne.montant) : '';
}

interface Props {
  payslipId: string;
  version: string | null;
  disabled?: boolean;
  forfaitJours?: boolean;
  onDemande: (demande: DemandeDeCorrection) => void;
}

export default function LignesDuBulletinCard({ payslipId, version, disabled, forfaitJours, onDemande }: Props) {
  const companyId = useActiveCompanyId();
  const [jeton, setJeton] = useState(1);
  const query = useQuery({
    queryKey: queryKeys.lignesCorrigeables(companyId, payslipId, version),
    queryFn: () => getLignesCorrigeables(payslipId, companyId),
    enabled: Boolean(companyId && payslipId),
    staleTime: 30_000,
  });
  const lignes = (query.data?.lignes ?? []).filter((l) => l.code);
  if (!query.isLoading && lignes.length === 0) return null;

  const demander = (demande: DemandeDeCorrection) => {
    setJeton(jeton + 1);
    onDemande(demande);
  };

  return (
    <Card data-testid="lignes-du-bulletin">
      <CardHeader>
        <CardTitle>Corriger le bulletin ligne à ligne</CardTitle>
        <CardDescription>
          « Corriger » change la ligne sur ce bulletin. « Régulariser un mois passé » ajoute une ligne de régularisation
          avec la période d’origine, que la DSN rattache à ces mois. Les deux s’ouvrent dans l’onglet « Corriger ».
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {query.isLoading ? <p className="text-sm text-muted-foreground">Lecture des lignes du bulletin…</p> : null}
        {BLOCS.map(({ bloc, titre }) => {
          const duBloc = lignes.filter((l) => l.bloc === bloc);
          if (duBloc.length === 0) return null;
          return (
            <div key={bloc} className="space-y-1">
              <p className="text-sm font-medium">{titre}</p>
              <ul className="divide-y rounded-md border">
                {duBloc.map((ligne) => {
                  const { corriger, regulariser } = gestesDeLaLigne(ligne, jeton, { forfaitJours });
                  return (
                    <li
                      key={String(ligne.code)}
                      className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
                      data-testid={`ligne-${ligne.code}`}
                    >
                      <span className="min-w-0">
                        <span className="font-medium">{ligne.libelle}</span>
                        {montantDe(ligne) ? (
                          <span className="ml-2 text-muted-foreground">{montantDe(ligne)}</span>
                        ) : null}
                        {!ligne.mode && ligne.raison ? (
                          <span className="block text-xs text-muted-foreground">{ligne.raison}</span>
                        ) : null}
                      </span>
                      {disabled ? null : (
                        <span className="flex shrink-0 gap-2">
                          {corriger ? (
                            <Button variant="outline" size="sm" onClick={() => demander(corriger)}>
                              <PencilLine className="h-4 w-4 mr-1" /> Corriger
                            </Button>
                          ) : null}
                          {regulariser ? (
                            <Button variant="outline" size="sm" onClick={() => demander(regulariser)}>
                              <History className="h-4 w-4 mr-1" /> Régulariser un mois passé
                            </Button>
                          ) : null}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
