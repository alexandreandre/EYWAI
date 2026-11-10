/**
 * Régularisations d'heures (retour d'Elsa, Lyon, 10/11/2026).
 *
 * Des heures d'un autre mois oubliées, ou payées en trop : on choisit le mois
 * d'origine, le taux et le nombre d'heures. Elles s'ajoutent aux heures du
 * planning, sur une ligne à elles, et gardent les exonérations des heures sup.
 */
import { useEffect, useRef, useState } from 'react';
import { History, Trash2, Undo2 } from 'lucide-react';

import type { NatureHeuresRegularisees } from '@/api/payslips';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  CE_QUI_SUIT_LA_CORRECTION,
  type DemandeDeCorrection,
  type EtatCorrections,
  moisPrecedent,
  NATURES_HEURES_REGULARISEES,
  periodeAffichee,
  periodeValide,
} from '@/features/payroll/utils/correctionsBulletin';
import { lireNombre } from '@/lib/nombreSaisi';

function euros(valeur: number): string {
  return valeur.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
}

function heures(valeur: number): string {
  return `${Math.round(valeur * 100) / 100}`.replace('.', ',');
}

interface Props {
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
  /** Mois du bulletin : le mois d'origine ne peut pas le dépasser. */
  year: number;
  month: number;
  /** Venue de l'onglet « Bulletin » : le taux des heures, pré-choisi. */
  demande?: DemandeDeCorrection | null;
  /** Temps partiel : les heures complémentaires d'abord, sans heures sup. */
  tempsPartiel?: boolean;
}

export default function RegularisationsHeuresCard({
  etat,
  onChange,
  disabled,
  year,
  month,
  demande,
  tempsPartiel = false,
}: Props) {
  const moisMax = `${year}-${String(month).padStart(2, '0')}`;
  const [mois, setMois] = useState(() => moisPrecedent(year, month));
  const [moisFin, setMoisFin] = useState('');
  const [nature, setNature] = useState<NatureHeuresRegularisees>(tempsPartiel ? 'hc1' : 'hs1');
  const [quantite, setQuantite] = useState('');
  const [taux, setTaux] = useState('');
  const [motif, setMotif] = useState('');
  const carte = useRef<HTMLDivElement>(null);
  const retirees = new Set(etat.heuresRegulariseesRetirees);

  useEffect(() => {
    if (demande?.carte !== 'heures') return;
    setNature(demande.nature);
    carte.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    // Le jeton change à chaque clic : la carte se rouvre même sur la même ligne.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demande?.jeton]);

  const valeur = lireNombre(quantite);
  const tauxSaisi = taux.trim() ? lireNombre(taux) : null;
  const tauxValide = !taux.trim() || (tauxSaisi !== null && tauxSaisi > 0);
  const moisValide = periodeValide({ debut: mois, fin: moisFin || mois }, moisMax);
  const pret =
    moisValide &&
    valeur !== null &&
    valeur !== 0 &&
    Math.abs(valeur) <= 300 &&
    tauxValide &&
    motif.trim().length >= 3;
  const natures = tempsPartiel
    ? NATURES_HEURES_REGULARISEES.filter((n) => !n.valeur.startsWith('hs'))
    : NATURES_HEURES_REGULARISEES.filter((n) => !n.valeur.startsWith('hc'));

  const ajouter = () => {
    if (!pret || valeur === null) return;
    onChange({
      ...etat,
      heuresRegulariseesAjoutees: [
        ...etat.heuresRegulariseesAjoutees,
        {
          nature,
          mois_origine: mois,
          ...(moisFin && moisFin !== mois ? { mois_fin: moisFin } : {}),
          quantite: Math.round(valeur * 100) / 100,
          motif: motif.trim(),
          taux_horaire: tauxSaisi,
        },
      ],
    });
    setQuantite('');
    setTaux('');
    setMotif('');
  };

  const nomDeNature = (n: NatureHeuresRegularisees) =>
    NATURES_HEURES_REGULARISEES.find((x) => x.valeur === n)?.libelle ?? n;

  return (
    <Card data-testid="regularisations-heures" ref={carte}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="h-5 w-5" />
          Régularisations d’heures
        </CardTitle>
        <CardDescription>
          Des heures d’un mois précédent oubliées, ou payées en trop ? Indiquez le mois d’origine, le taux et le
          nombre d’heures (négatif pour reprendre). Elles s’ajoutent aux heures du planning sur une ligne à part, et
          les heures sup gardent leurs exonérations. {CE_QUI_SUIT_LA_CORRECTION}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {etat.heuresRegularisees.map((r) => (
          <div key={r.saisieId} className="flex items-center justify-between rounded-md border p-3 text-sm">
            <div className={retirees.has(r.saisieId) ? 'line-through text-muted-foreground' : ''}>
              <div className="font-medium">{r.libelle}</div>
              <div className="text-xs text-muted-foreground">
                {heures(r.quantite)} h × {r.taux.toLocaleString('fr-FR')} € = {euros(r.montant)} — {r.motif}
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
                    heuresRegulariseesRetirees: etat.heuresRegulariseesRetirees.filter((id) => id !== r.saisieId),
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
                  onChange({ ...etat, heuresRegulariseesRetirees: [...etat.heuresRegulariseesRetirees, r.saisieId] })
                }
              >
                <Trash2 className="h-4 w-4 mr-1" /> Retirer
              </Button>
            )}
          </div>
        ))}
        {etat.heuresRegulariseesAjoutees.map((r, index) => (
          <div
            key={`nouvelle-${index}`}
            className="flex items-center justify-between rounded-md border border-dashed p-3 text-sm"
          >
            <div>
              <div className="font-medium">
                {heures(r.quantite)} h de {periodeAffichee(r.mois_origine, r.mois_fin)} — {nomDeNature(r.nature)} (à
                enregistrer)
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
                  heuresRegulariseesAjoutees: etat.heuresRegulariseesAjoutees.filter((_, i) => i !== index),
                })
              }
            >
              <Trash2 className="h-4 w-4 mr-1" /> Annuler
            </Button>
          </div>
        ))}
        {!disabled ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="regul-heures-mois">Mois d’origine des heures (à partir de)</Label>
              <Input
                id="regul-heures-mois"
                type="month"
                max={moisMax}
                value={mois}
                onChange={(e) => setMois(e.target.value)}
              />
              {mois && !moisValide ? (
                <p className="text-xs text-destructive">
                  La période doit aller d’un mois à un mois égal ou suivant, sans dépasser celui du bulletin.
                </p>
              ) : null}
            </div>
            <div className="space-y-1">
              <Label htmlFor="regul-heures-mois-fin">Jusqu’au mois (si plusieurs mois)</Label>
              <Input
                id="regul-heures-mois-fin"
                type="month"
                min={mois}
                max={moisMax}
                value={moisFin}
                onChange={(e) => setMoisFin(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="regul-heures-nature">Taux</Label>
              <select
                id="regul-heures-nature"
                className="w-full rounded-md border px-2 py-2 text-sm"
                value={nature}
                onChange={(e) => setNature(e.target.value as NatureHeuresRegularisees)}
              >
                {natures.map((n) => (
                  <option key={n.valeur} value={n.valeur}>
                    {n.libelle}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="regul-heures-quantite">Nombre d’heures (négatif pour reprendre)</Label>
              <Input
                id="regul-heures-quantite"
                inputMode="decimal"
                value={quantite}
                onChange={(e) => setQuantite(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="regul-heures-taux">Taux horaire de base du mois d’origine (si différent)</Label>
              <Input
                id="regul-heures-taux"
                inputMode="decimal"
                placeholder="Vide : celui du bulletin"
                value={taux}
                onChange={(e) => setTaux(e.target.value)}
              />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="regul-heures-motif">Motif (obligatoire)</Label>
              <Input
                id="regul-heures-motif"
                maxLength={300}
                value={motif}
                onChange={(e) => setMotif(e.target.value)}
              />
            </div>
            <div className="sm:col-span-2">
              <Button variant="outline" disabled={!pret} onClick={ajouter} data-testid="ajouter-regularisation-heures">
                Ajouter les heures
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
