/**
 * Régularisations de cotisation.
 *
 * Une cotisation fausse se corrige ici : on choisit l'organisme, on tape l'écart
 * en euros et un motif. Il devient une base au taux de la cotisation, le serveur
 * recalcule le bulletin en entier, et la régularisation passe dans le net, les
 * cumuls, la DSN et les exports.
 *
 * Pour un mois passé (page client du 10/11), on saisit la période corrigée,
 * comme « À partir du bulletin de … Jusqu'au bulletin de … » : elle s'imprime
 * dans le libellé et la DSN rattache la régularisation à ces mois.
 */
import { useEffect, useRef, useState } from 'react';
import { Scale, Trash2, Undo2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  CE_QUI_SUIT_LA_CORRECTION,
  cotisationsRegularisables,
  type DemandeDeCorrection,
  type EtatCorrections,
  moisPrecedent,
  type PartRegularisee,
  periodeAffichee,
  periodeValide,
  regularisationDepuisEcart,
} from '@/features/payroll/utils/correctionsBulletin';
import { lireNombre } from '@/lib/nombreSaisi';

function euros(valeur: number): string {
  return valeur.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
}

interface Props {
  payslipData: unknown;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
  /** Mois du bulletin : la période corrigée ne peut pas le dépasser. */
  year: number;
  month: number;
  /** Venue de l'onglet « Bulletin » : la cotisation à régulariser, pré-choisie. */
  demande?: DemandeDeCorrection | null;
}

export default function RegularisationsCotisationCard({
  payslipData,
  etat,
  onChange,
  disabled,
  year,
  month,
  demande,
}: Props) {
  const cotisations = cotisationsRegularisables(payslipData);
  const moisMax = `${year}-${String(month).padStart(2, '0')}`;
  const [choix, setChoix] = useState(0);
  const [ecart, setEcart] = useState('');
  const [part, setPart] = useState<PartRegularisee>('les_deux');
  const [motif, setMotif] = useState('');
  const [moisPasse, setMoisPasse] = useState(false);
  const [debut, setDebut] = useState(() => moisPrecedent(year, month));
  const [fin, setFin] = useState(() => moisPrecedent(year, month));
  const carte = useRef<HTMLDivElement>(null);
  const retirees = new Set(etat.regularisationsRetirees);
  const cotisation = cotisations[choix];
  const valeur = lireNombre(ecart);
  const periode = moisPasse ? { debut, fin: fin || debut } : null;
  const periodeOk = !periode || periodeValide(periode, moisMax);
  const pret = !!cotisation && valeur !== null && valeur !== 0 && motif.trim().length >= 3 && periodeOk;

  useEffect(() => {
    if (demande?.carte !== 'cotisation') return;
    const index = cotisations.findIndex((c) => c.cotiId === demande.cotiId && c.libelle === demande.libelle);
    const repli = cotisations.findIndex((c) => c.cotiId === demande.cotiId);
    if (index >= 0 || repli >= 0) setChoix(index >= 0 ? index : repli);
    setMoisPasse(true);
    carte.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    // Le jeton change à chaque clic : la carte se rouvre même sur la même ligne.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demande?.jeton]);

  const ajouter = () => {
    if (!pret || !cotisation || valeur === null) return;
    onChange({
      ...etat,
      regularisationsAjoutees: [
        ...etat.regularisationsAjoutees,
        regularisationDepuisEcart(cotisation, valeur, part, motif, periode),
      ],
    });
    setEcart('');
    setMotif('');
  };

  return (
    <Card data-testid="regularisations-cotisation" ref={carte}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Scale className="h-5 w-5" />
          Régularisations de cotisation
        </CardTitle>
        <CardDescription>
          Une cotisation fausse ? Choisissez-la, tapez l’écart en euros et le motif. Pour un mois passé, indiquez
          la période corrigée : elle s’imprime sur la ligne et la DSN rattache la régularisation à ces mois.{' '}
          {CE_QUI_SUIT_LA_CORRECTION}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {etat.regularisations.map((r) => (
          <div key={r.saisieId} className="flex items-center justify-between rounded-md border p-3 text-sm">
            <div className={retirees.has(r.saisieId) ? 'line-through text-muted-foreground' : ''}>
              <div className="font-medium">{r.libelle}</div>
              <div className="text-xs text-muted-foreground">
                {r.motif} — salarial {euros(r.montantSalarial)}, patronal {euros(r.montantPatronal)}
              </div>
            </div>
            {retirees.has(r.saisieId) ? (
              <Button
                variant="ghost"
                size="sm"
                disabled={disabled}
                onClick={() =>
                  onChange({
                    ...etat,
                    regularisationsRetirees: etat.regularisationsRetirees.filter((id) => id !== r.saisieId),
                  })
                }
              >
                <Undo2 className="h-4 w-4 mr-1" /> Garder
              </Button>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                disabled={disabled}
                onClick={() =>
                  onChange({ ...etat, regularisationsRetirees: [...etat.regularisationsRetirees, r.saisieId] })
                }
              >
                <Trash2 className="h-4 w-4 mr-1" /> Retirer
              </Button>
            )}
          </div>
        ))}
        {etat.regularisationsAjoutees.map((r, index) => (
          <div
            key={`nouvelle-${index}`}
            className="flex items-center justify-between rounded-md border border-dashed p-3 text-sm"
          >
            <div>
              <div className="font-medium">
                {r.libelle}
                {r.mois_debut ? ` – ${periodeAffichee(r.mois_debut, r.mois_fin)}` : ''} (à enregistrer)
              </div>
              <div className="text-xs text-muted-foreground">{r.motif}</div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              disabled={disabled}
              onClick={() =>
                onChange({
                  ...etat,
                  regularisationsAjoutees: etat.regularisationsAjoutees.filter((_, i) => i !== index),
                })
              }
            >
              <Trash2 className="h-4 w-4 mr-1" /> Annuler
            </Button>
          </div>
        ))}
        {!disabled && cotisations.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="regul-cotisation">Cotisation</Label>
              <select
                id="regul-cotisation"
                className="w-full rounded-md border px-2 py-2 text-sm"
                value={choix}
                onChange={(e) => setChoix(Number(e.target.value))}
              >
                {cotisations.map((c, i) => (
                  <option key={`${c.cotiId}-${i}`} value={i}>
                    {c.libelle}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="regul-part">Part à régulariser</Label>
              <select
                id="regul-part"
                className="w-full rounded-md border px-2 py-2 text-sm"
                value={part}
                onChange={(e) => setPart(e.target.value as PartRegularisee)}
              >
                <option value="les_deux">Les deux parts</option>
                <option value="salariale">La part salariale</option>
                <option value="patronale">La part patronale</option>
              </select>
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="regul-periode">Période corrigée</Label>
              <select
                id="regul-periode"
                className="w-full rounded-md border px-2 py-2 text-sm"
                value={moisPasse ? 'passe' : 'bulletin'}
                onChange={(e) => setMoisPasse(e.target.value === 'passe')}
              >
                <option value="bulletin">Le mois de ce bulletin</option>
                <option value="passe">Un ou plusieurs mois passés</option>
              </select>
              {moisPasse ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <Label htmlFor="regul-debut">À partir du bulletin de</Label>
                    <Input
                      id="regul-debut"
                      type="month"
                      max={moisMax}
                      value={debut}
                      onChange={(e) => {
                        setDebut(e.target.value);
                        if (!fin || fin < e.target.value) setFin(e.target.value);
                      }}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="regul-fin">Jusqu’au bulletin de</Label>
                    <Input id="regul-fin" type="month" max={moisMax} value={fin} onChange={(e) => setFin(e.target.value)} />
                  </div>
                  {!periodeOk ? (
                    <p className="text-xs text-destructive sm:col-span-2">
                      La période doit aller d’un mois à un mois égal ou suivant, sans dépasser celui du bulletin.
                    </p>
                  ) : periode && periode.debut !== periode.fin ? (
                    <p className="text-xs text-muted-foreground sm:col-span-2">
                      Sur plusieurs mois, la DSN répartit l’écart à parts égales. Pour une autre répartition, saisissez
                      une régularisation par mois.
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="space-y-1">
              <Label htmlFor="regul-ecart">Écart en euros (négatif pour baisser)</Label>
              <Input id="regul-ecart" inputMode="decimal" value={ecart} onChange={(e) => setEcart(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="regul-motif">Motif (obligatoire)</Label>
              <Input id="regul-motif" maxLength={300} value={motif} onChange={(e) => setMotif(e.target.value)} />
            </div>
            <div className="sm:col-span-2">
              <Button variant="outline" disabled={!pret} onClick={ajouter} data-testid="ajouter-regularisation">
                Ajouter la régularisation
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
