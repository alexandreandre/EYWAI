/** « Ajouter une ligne » : quatre tuiles dans les mots de la RH, deux champs au plus. */
import { useEffect, useRef, useState } from 'react';
import { ArrowLeftRight, Clock, Coins, Percent, Plus } from 'lucide-react';

import AjouterPrimeBouton from '@/components/payslip-edit/AjouterPrimeBouton';
import RegularisationsCotisationCard from '@/components/payslip-edit/RegularisationsCotisationCard';
import RegularisationsHeuresCard from '@/components/payslip-edit/RegularisationsHeuresCard';
import { type DemandeDeCorrection, type EtatCorrections } from '@/features/payroll/utils/correctionsBulletin';
import { PHRASE_FORFAIT_JOURS_SANS_HEURES_SUP } from '@/lib/forfaitJoursAffichage';
import { cn } from '@/lib/utils';
import HeuresDuMois from './HeuresDuMois';
import SurLeNetFormulaire from './SurLeNetFormulaire';

export type Tuile = 'heures' | 'prime' | 'net' | 'cotisation';

interface Props {
  payslipData: unknown;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
  forfaitJours?: boolean;
  tempsPartiel?: boolean;
  employeeId: string;
  year: number;
  month: number;
  demande?: DemandeDeCorrection | null;
  /** La demande de l'onglet « Bulletin » est consommée : elle ne se rouvre plus au remontage. */
  onDemandeTraitee?: () => void;
}

export default function AjouterUneLigne(props: Props) {
  const { etat, onChange, disabled, forfaitJours, tempsPartiel, employeeId, year, month, demande, payslipData } = props;
  const [ouvert, setOuvert] = useState(false);
  const [tuile, setTuile] = useState<Tuile | null>(null);
  const [moisDesHeures, setMoisDesHeures] = useState<'ce_mois' | 'passe'>('ce_mois');
  // La demande prise ici, gardée pour la carte qui se pré-remplit : celle de la
  // page est vidée aussitôt, pour ne pas rouvrir la tuile à chaque remontage.
  const [demandePrise, setDemandePrise] = useState<DemandeDeCorrection | null>(null);
  const racine = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // L'onglet « Bulletin » demande une régularisation : la bonne tuile s'ouvre.
    if (demande?.carte === 'heures') {
      setOuvert(true);
      setTuile('heures');
      setMoisDesHeures('passe');
    } else if (demande?.carte === 'cotisation') {
      setOuvert(true);
      setTuile('cotisation');
    } else return;
    setDemandePrise(demande);
    props.onDemandeTraitee?.();
    racine.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demande?.jeton]);

  if (disabled) return null;
  const heures = tempsPartiel ? 'heures complémentaires' : 'heures sup';
  const tuiles: Array<{ cle: Tuile; titre: string; aide: string; Icone: typeof Clock }> = [
    { cle: 'heures', titre: 'Des heures', aide: `en plus ou en moins, ce mois-ci (${heures}) ou un mois passé`, Icone: Clock },
    { cle: 'prime', titre: 'Une prime', aide: '13e mois, panier, rappel de maintien… ou une prime libre', Icone: Coins },
    { cle: 'net', titre: 'Sur le net', aide: 'remboursement de frais, retenue', Icone: ArrowLeftRight },
    { cle: 'cotisation', titre: 'Une cotisation', aide: 'd’un mois passé, oubliée ou fausse', Icone: Percent },
  ];

  return (
    <div ref={racine} className="space-y-3 p-3">
      <button
        type="button"
        data-testid="ajouter-une-ligne"
        onClick={() => setOuvert(!ouvert)}
        className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-blue-500 bg-blue-50 py-2.5 font-semibold text-blue-700 dark:bg-blue-950/30 dark:text-blue-300"
      >
        <Plus className="h-4 w-4" /> Ajouter une ligne
      </button>
      {ouvert ? (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {tuiles.map(({ cle, titre, aide, Icone }) => (
            <button
              key={cle}
              type="button"
              data-testid={`tuile-${cle}`}
              aria-pressed={tuile === cle}
              onClick={() => setTuile(tuile === cle ? null : cle)}
              className={cn(
                'rounded-lg border p-3 text-left',
                tuile === cle ? 'border-2 border-blue-600 bg-blue-50 dark:bg-blue-950/30' : 'bg-background'
              )}
            >
              <span className="flex items-center gap-2 font-semibold">
                <Icone className="h-4 w-4" /> {titre}
              </span>
              <span className="mt-1 block text-xs text-muted-foreground">{aide}</span>
            </button>
          ))}
        </div>
      ) : null}

      {ouvert && tuile === 'heures' ? (
        <div className="space-y-3 rounded-lg border bg-background p-3">
          {forfaitJours ? (
            <p className="text-sm" data-testid="forfait-jours-sans-heures-sup">{PHRASE_FORFAIT_JOURS_SANS_HEURES_SUP}</p>
          ) : (
            <>
              <div className="inline-flex overflow-hidden rounded-md border text-sm">
                <button
                  type="button"
                  data-testid="heures-ce-mois"
                  aria-pressed={moisDesHeures === 'ce_mois'}
                  onClick={() => setMoisDesHeures('ce_mois')}
                  className={cn('px-3 py-1', moisDesHeures === 'ce_mois' ? 'bg-primary text-primary-foreground' : 'bg-background')}
                >
                  Ce mois-ci
                </button>
                <button
                  type="button"
                  data-testid="heures-mois-passe"
                  aria-pressed={moisDesHeures === 'passe'}
                  onClick={() => setMoisDesHeures('passe')}
                  className={cn('px-3 py-1', moisDesHeures === 'passe' ? 'bg-primary text-primary-foreground' : 'bg-background')}
                >
                  Un mois passé
                </button>
              </div>
              {moisDesHeures === 'ce_mois' ? (
                <HeuresDuMois payslipData={payslipData} etat={etat} onChange={onChange} tempsPartiel={tempsPartiel} />
              ) : (
                <RegularisationsHeuresCard
                  etat={etat}
                  onChange={onChange}
                  year={year}
                  month={month}
                  demande={demandePrise}
                  tempsPartiel={tempsPartiel}
                />
              )}
            </>
          )}
        </div>
      ) : null}
      {ouvert && tuile === 'prime' ? (
        <div className="rounded-lg border bg-background p-3">
          <AjouterPrimeBouton
            employeeId={employeeId}
            year={year}
            month={month}
            onAjout={(primes) => onChange({ ...etat, primesAjoutees: [...etat.primesAjoutees, ...primes] })}
          />
        </div>
      ) : null}
      {ouvert && tuile === 'net' ? (
        <div className="rounded-lg border bg-background p-3">
          <SurLeNetFormulaire onAjout={(prime) => onChange({ ...etat, primesAjoutees: [...etat.primesAjoutees, prime] })} />
        </div>
      ) : null}
      {ouvert && tuile === 'cotisation' ? (
        <RegularisationsCotisationCard
          payslipData={payslipData}
          etat={etat}
          onChange={onChange}
          year={year}
          month={month}
          demande={demandePrise}
        />
      ) : null}
    </div>
  );
}
