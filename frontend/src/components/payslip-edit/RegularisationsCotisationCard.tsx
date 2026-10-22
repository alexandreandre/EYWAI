/**
 * Régularisations de cotisation.
 *
 * Une cotisation fausse se corrige ici : on choisit l'organisme, on tape l'écart
 * en euros et un motif. Il devient une base au taux de la cotisation, le serveur
 * recalcule le bulletin en entier, et la régularisation passe dans le net, les
 * cumuls, la DSN et les exports.
 */
import { useState } from 'react';
import { Scale, Trash2, Undo2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  cotisationsRegularisables,
  type EtatCorrections,
  type PartRegularisee,
  regularisationDepuisEcart,
} from '@/features/payroll/utils/correctionsBulletin';

function euros(valeur: number): string {
  return valeur.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
}

interface Props {
  payslipData: unknown;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
}

export default function RegularisationsCotisationCard({ payslipData, etat, onChange, disabled }: Props) {
  const cotisations = cotisationsRegularisables(payslipData);
  const [choix, setChoix] = useState(0);
  const [ecart, setEcart] = useState('');
  const [part, setPart] = useState<PartRegularisee>('les_deux');
  const [motif, setMotif] = useState('');
  const retirees = new Set(etat.regularisationsRetirees);
  const cotisation = cotisations[choix];
  const valeur = Number.parseFloat(ecart.replace(',', '.'));
  const pret = !!cotisation && Number.isFinite(valeur) && valeur !== 0 && motif.trim().length >= 3;

  const ajouter = () => {
    if (!pret || !cotisation) return;
    onChange({
      ...etat,
      regularisationsAjoutees: [
        ...etat.regularisationsAjoutees,
        regularisationDepuisEcart(cotisation, valeur, part, motif),
      ],
    });
    setEcart('');
    setMotif('');
  };

  return (
    <Card data-testid="regularisations-cotisation">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Scale className="h-5 w-5" />
          Régularisations de cotisation
        </CardTitle>
        <CardDescription>
          Une cotisation fausse ? Choisissez-la, tapez l’écart en euros et le motif. À l’enregistrement, le
          bulletin est recalculé en entier : net, cumuls, DSN et exports suivent.
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
              <div className="font-medium">{r.libelle} (à enregistrer)</div>
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
