/** Les heures du mois : heures sup, ou heures complémentaires à temps partiel. */
import { useEffect, useRef, useState } from 'react';
import { CalendarDays, Undo2 } from 'lucide-react';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  descriptionHeuresSupDuMois,
  type EtatCorrections,
  heuresComplementairesDeclarees,
  heuresDeclarees,
  paliersHeuresComplementaires,
} from '@/features/payroll/utils/correctionsBulletin';
import { lireNombre } from '@/lib/nombreSaisi';

function texteDe(valeur: number): string {
  return Number.isFinite(valeur) ? String(valeur) : '';
}

function lire(texte: string): number {
  const valeur = lireNombre(texte);
  return valeur !== null && valeur >= 0 ? valeur : 0;
}

function lireSigne(texte: string): number {
  return lireNombre(texte) ?? 0;
}

/** Champ numérique qui laisse effacer et retaper (« 3, », « - ») sans sauter à zéro. */
export function ChampNombre({
  id,
  valeur,
  onValeur,
  disabled,
  suffixe,
  testId,
  negatifPermis = false,
}: {
  id: string;
  valeur: number;
  onValeur: (valeur: number) => void;
  disabled?: boolean;
  suffixe: string;
  testId?: string;
  negatifPermis?: boolean;
}) {
  const [texte, setTexte] = useState(texteDe(valeur));
  const dernierEmis = useRef(valeur);
  useEffect(() => {
    // Ne resynchronise que sur une valeur venue d'ailleurs (rechargement,
    // annulation) : pas sur celle que la frappe vient d'émettre.
    if (Math.abs(valeur - dernierEmis.current) > 0.0001) {
      dernierEmis.current = valeur;
      setTexte(texteDe(valeur));
    }
  }, [valeur]);
  return (
    <div className="flex items-center gap-2">
      <Input
        id={id}
        data-testid={testId}
        inputMode="decimal"
        className="w-28 text-right"
        value={texte}
        disabled={disabled}
        onChange={(e) => {
          setTexte(e.target.value);
          const lu = negatifPermis ? lireSigne(e.target.value) : lire(e.target.value);
          dernierEmis.current = lu;
          onValeur(lu);
        }}
      />
      <span className="text-sm text-muted-foreground">{suffixe}</span>
    </div>
  );
}

function heures(valeur: number): string {
  return `${Math.round(valeur * 100) / 100}`.replace('.', ',');
}

interface Props {
  payslipData: unknown;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
  tempsPartiel?: boolean;
}

export default function HeuresDuMois({ payslipData, etat, onChange, disabled, tempsPartiel = false }: Props) {
  const declarees = heuresDeclarees(payslipData);
  const hcDeclarees = heuresComplementairesDeclarees(payslipData);
  const [palier1, palier2] = paliersHeuresComplementaires(payslipData);
  const maj = (changement: Partial<EtatCorrections>) => onChange({ ...etat, ...changement });
  return tempsPartiel ? (
    <div className="space-y-4" data-testid="heures-complementaires-du-mois">
      <p className="text-xs text-muted-foreground">
        Temps partiel : les heures au-delà de l’horaire du contrat sont des heures complémentaires, majorées à {palier1} %
        jusqu’au dixième des heures du contrat, à {palier2} % au-delà. Déclarées ici, elles remplacent celles du planning
        pour ce bulletin, même à zéro. À l’enregistrement, le bulletin est recalculé en entier.
      </p>
      {hcDeclarees && !etat.hcAuPlanning ? (
        <Alert data-testid="heures-complementaires-declarees">
          <AlertDescription>
            Heures déclarées au bulletin : {heures(hcDeclarees.hs25)} h à {palier1} %, {heures(hcDeclarees.hs50)} h à{' '}
            {palier2} % (le planning en donnait {heures(hcDeclarees.planning)} h).
          </AlertDescription>
        </Alert>
      ) : null}
      {etat.hcAuPlanning ? (
        <Alert>
          <AlertDescription className="flex flex-wrap items-center justify-between gap-2">
            <span>Les heures complémentaires du planning seront reprises au recalcul.</span>
            <Button variant="outline" size="sm" disabled={disabled} onClick={() => maj({ hcAuPlanning: false })}>
              <Undo2 className="h-4 w-4 mr-2" />
              Annuler
            </Button>
          </AlertDescription>
        </Alert>
      ) : (
        <div className="flex flex-wrap items-end gap-6">
          <div className="space-y-1">
            <Label htmlFor="hc1">Majorées à {palier1} %</Label>
            <ChampNombre
              id="hc1"
              testId="heures-complementaires-1"
              valeur={etat.hc1}
              onValeur={(hc1) => maj({ hc1 })}
              disabled={disabled}
              suffixe="h"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="hc2">Majorées à {palier2} %</Label>
            <ChampNombre
              id="hc2"
              testId="heures-complementaires-2"
              valeur={etat.hc2}
              onValeur={(hc2) => maj({ hc2 })}
              disabled={disabled}
              suffixe="h"
            />
          </div>
          {hcDeclarees ? (
            <Button variant="outline" size="sm" disabled={disabled} onClick={() => maj({ hcAuPlanning: true })}>
              <CalendarDays className="h-4 w-4 mr-2" />
              Reprendre les heures du planning
            </Button>
          ) : null}
        </div>
      )}
    </div>
  ) : (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">{descriptionHeuresSupDuMois(payslipData)}</p>
      {declarees && !etat.revenirAuPlanning ? (
        <Alert data-testid="heures-declarees">
          <AlertDescription>
            Heures déclarées au bulletin : {heures(declarees.hs25)} h à 25 %, {heures(declarees.hs50)} h à 50 % (le planning
            en donnait {heures(declarees.planning)} h).
          </AlertDescription>
        </Alert>
      ) : null}
      {etat.revenirAuPlanning ? (
        <Alert data-testid="retour-planning">
          <AlertDescription className="flex flex-wrap items-center justify-between gap-2">
            <span>Les heures du planning seront reprises au recalcul.</span>
            <Button variant="outline" size="sm" disabled={disabled} onClick={() => maj({ revenirAuPlanning: false })}>
              <Undo2 className="h-4 w-4 mr-2" />
              Annuler
            </Button>
          </AlertDescription>
        </Alert>
      ) : (
        <div className="flex flex-wrap items-end gap-6">
          <div className="space-y-1">
            <Label htmlFor="hs25">Majorées à 25 %</Label>
            <ChampNombre
              id="hs25"
              testId="heures-sup-25"
              valeur={etat.hs25}
              onValeur={(hs25) => maj({ hs25 })}
              disabled={disabled}
              suffixe="h"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="hs50">Majorées à 50 %</Label>
            <ChampNombre
              id="hs50"
              testId="heures-sup-50"
              valeur={etat.hs50}
              onValeur={(hs50) => maj({ hs50 })}
              disabled={disabled}
              suffixe="h"
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            data-testid="revenir-au-planning"
            disabled={disabled}
            onClick={() => maj({ revenirAuPlanning: true })}
          >
            <CalendarDays className="h-4 w-4 mr-2" />
            Reprendre les heures du planning
          </Button>
        </div>
      )}
    </div>
  );
}
