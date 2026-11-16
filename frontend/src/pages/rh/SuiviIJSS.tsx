import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { RhPageHeader } from '@/components/layout';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { ArretsDuMoisPanel } from '@/features/ijss/components/ArretsDuMoisPanel';
import { AbsenceRequestModal } from '@/components/AbsenceRequestModal';

const MONTHS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
];

/**
 * Étape ③ du mode paie, « Arrêts & IJ » (retour d'Elsa du 16/11) : on
 * enregistre l'arrêt (subrogation oui ou non), on joint les pièces si on veut,
 * on dit « IJ reçues ». Pas d'import, pas d'export : le rapprochement par
 * fichiers CPAM ou bancaires est retiré de l'écran.
 */
export default function SuiviIJSSPage() {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [saisieArretOuverte, setSaisieArretOuverte] = useState(false);

  const yearOptions = useMemo(() => {
    const y = new Date().getFullYear();
    return [y - 1, y, y + 1];
  }, []);

  return (
    <div className="space-y-6">
      <RhPageHeader
        title="Arrêts & IJ"
        description="Les arrêts, la subrogation, les IJ reçues et le maintien de salaire, au même endroit."
        actions={
          <Button type="button" onClick={() => setSaisieArretOuverte(true)}>
            + Enregistrer un arrêt
          </Button>
        }
      />
      <AbsenceRequestModal
        mode="rh_arret"
        isOpen={saisieArretOuverte}
        onClose={() => setSaisieArretOuverte(false)}
        onSuccess={() => {
          setSaisieArretOuverte(false);
          void queryClient.invalidateQueries({ queryKey: ['arrets-du-mois', companyId] });
        }}
      />

      <Card className="border-dashed">
        <CardContent className="pt-6 text-sm text-muted-foreground">
          <ol className="list-decimal list-inside space-y-1">
            <li>
              <span className="text-foreground">Enregistrez l&apos;arrêt</span> et dites s&apos;il y a
              subrogation (la société reçoit les IJ à la place du salarié).
            </li>
            <li>
              <span className="text-foreground">Joignez les pièces si vous les avez</span> : virement de la
              CPAM, IJ transmises par le salarié, décompte. C&apos;est facultatif.
            </li>
            <li>
              <span className="text-foreground">Quand les IJ sont reçues, cliquez sur « Reçues »</span> :
              Martine retient le montant qu&apos;elle a estimé et verse le maintien sur le bulletin. Pour
              un autre montant, ouvrez la ligne de l&apos;arrêt.
            </li>
          </ol>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <p className="mb-1 text-xs text-muted-foreground">Année</p>
          <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
            <SelectTrigger className="w-[100px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {yearOptions.map((y) => (
                <SelectItem key={y} value={String(y)}>
                  {y}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <p className="mb-1 text-xs text-muted-foreground">Mois</p>
          <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
            <SelectTrigger className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MONTHS.map((label, i) => (
                <SelectItem key={label} value={String(i + 1)}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <ArretsDuMoisPanel year={year} month={month} libelleMois={`${MONTHS[month - 1]} ${year}`} />
    </div>
  );
}
