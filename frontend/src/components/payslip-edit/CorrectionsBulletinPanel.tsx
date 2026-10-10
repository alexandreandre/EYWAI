// frontend/src/components/payslip-edit/CorrectionsBulletinPanel.tsx

/**
 * Ce qui se corrige depuis le bulletin : ses heures sup et ses primes du mois.
 *
 * Chaque correction devient une variable du mois et le bulletin est recalculé
 * en entier à l'enregistrement (brut, cotisations, net, cumuls). Le reste se
 * corrige à sa source ; l'encart du bas y mène.
 */

import { useEffect, useRef, useState } from 'react';
import { CalendarDays, Clock, Coins, ExternalLink, Trash2, Undo2, UserRound, SlidersHorizontal } from 'lucide-react';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import AjouterPrimeBouton from '@/components/payslip-edit/AjouterPrimeBouton';
import { pastilleSoumise } from '@/components/saisies/libellesSaisie';
import {
  heuresDeclarees,
  type EtatCorrections,
  montantCorrigeDeLaPrime,
} from '@/features/payroll/utils/correctionsBulletin';

function texteDe(valeur: number): string {
  return Number.isFinite(valeur) ? String(valeur) : '';
}

function lire(texte: string): number {
  const valeur = Number.parseFloat(texte.replace(',', '.'));
  return Number.isFinite(valeur) && valeur >= 0 ? valeur : 0;
}

function lireSigne(texte: string): number {
  const valeur = Number.parseFloat(texte.replace(',', '.'));
  return Number.isFinite(valeur) ? valeur : 0;
}

/** Champ numérique qui laisse effacer et retaper (« 3, », « - ») sans sauter à zéro. */
function ChampNombre({
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

function euros(valeur: number): string {
  return valeur.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
}

interface Props {
  payslipData: unknown;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
  employeeId: string;
  year: number;
  month: number;
  lienPlanning: string;
  lienFiche: string;
  lienSaisies: string;
  /** Passe par la garde des corrections non enregistrées avant de quitter l'écran. */
  onAller: (lien: string) => void;
}

export default function CorrectionsBulletinPanel({
  payslipData,
  etat,
  onChange,
  disabled,
  employeeId,
  year,
  month,
  lienPlanning,
  lienFiche,
  lienSaisies,
  onAller,
}: Props) {
  const declarees = heuresDeclarees(payslipData);
  const retirees = new Set(etat.primesRetirees);
  const maj = (changement: Partial<EtatCorrections>) => onChange({ ...etat, ...changement });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Heures supplémentaires du mois
          </CardTitle>
          <CardDescription>
            Déclarées ici, elles remplacent celles du planning pour ce bulletin, même à zéro.
            À l’enregistrement, le bulletin est recalculé en entier.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {declarees && !etat.revenirAuPlanning ? (
            <Alert data-testid="heures-declarees">
              <AlertDescription>
                Heures déclarées au bulletin : {heures(declarees.hs25)} h à 25 %,{' '}
                {heures(declarees.hs50)} h à 50 % (le planning en donnait {heures(declarees.planning)} h).
              </AlertDescription>
            </Alert>
          ) : null}
          {etat.revenirAuPlanning ? (
            <Alert data-testid="retour-planning">
              <AlertDescription className="flex flex-wrap items-center justify-between gap-2">
                <span>Les heures du planning seront reprises au recalcul.</span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={disabled}
                  onClick={() => maj({ revenirAuPlanning: false })}
                >
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
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Coins className="h-5 w-5" />
            Primes du mois
          </CardTitle>
          <CardDescription>
            Les primes saisies pour ce mois. Corrigez un montant, retirez ou ajoutez une prime :
            elle devient une variable du mois et le bulletin est recalculé.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {etat.primes.length === 0 && etat.primesAjoutees.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune prime saisie pour ce mois.</p>
          ) : null}
          {etat.primes.map((prime) => {
            const retiree = retirees.has(prime.saisieId);
            return (
              <div
                key={prime.saisieId}
                data-testid={`prime-${prime.saisieId}`}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3"
              >
                <div className="flex items-center gap-2">
                  <span className={retiree ? 'line-through text-muted-foreground' : 'font-medium'}>
                    {prime.libelle}
                  </span>
                  <Badge variant="secondary">
                    {prime.surLeNet === 'retenue'
                      ? 'Retenue sur le net'
                      : prime.surLeNet === 'versement'
                        ? 'Versement sur le net'
                        : pastilleSoumise(prime.soumise)}
                  </Badge>
                </div>
                {retiree ? (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={disabled}
                    onClick={() =>
                      maj({ primesRetirees: etat.primesRetirees.filter((id) => id !== prime.saisieId) })
                    }
                  >
                    <Undo2 className="h-4 w-4 mr-2" />
                    Garder
                  </Button>
                ) : (
                  <div className="flex items-center gap-2">
                    <ChampNombre
                      id={`montant-${prime.saisieId}`}
                      // Une retenue s'affiche en positif (« 200 € retenus ») et reste
                      // négative dans la saisie.
                      valeur={prime.surLeNet === 'retenue' ? Math.abs(prime.montant) : prime.montant}
                      negatifPermis={!prime.surLeNet}
                      onValeur={(saisi) => {
                        const montant = montantCorrigeDeLaPrime(prime, saisi);
                        maj({
                          primes: etat.primes.map((p) =>
                            p.saisieId === prime.saisieId ? { ...p, montant } : p
                          ),
                        });
                      }}
                      disabled={disabled}
                      suffixe="€"
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Retirer ${prime.libelle}`}
                      disabled={disabled}
                      onClick={() => maj({ primesRetirees: [...etat.primesRetirees, prime.saisieId] })}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
          {etat.primesAjoutees.map((prime, index) => (
            <div
              key={`ajoutee-${index}`}
              className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-dashed p-3"
            >
              <div className="flex items-center gap-2">
                <span className="font-medium">{prime.name}</span>
                <Badge variant="outline">Ajoutée</Badge>
                <Badge variant="secondary">{prime.sur_le_net ? 'Sur le net' : pastilleSoumise(prime.is_socially_taxed)}</Badge>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm">{euros(prime.amount)}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Ne pas ajouter ${prime.name}`}
                  disabled={disabled}
                  onClick={() =>
                    maj({ primesAjoutees: etat.primesAjoutees.filter((_, i) => i !== index) })
                  }
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
          {!disabled ? (
            <AjouterPrimeBouton
              employeeId={employeeId}
              year={year}
              month={month}
              onAjout={(primes) => maj({ primesAjoutees: [...etat.primesAjoutees, ...primes] })}
            />
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Ce qui se corrige ailleurs</CardTitle>
          <CardDescription>
            Le bulletin se recalcule depuis ces écrans : corrigez à la source, puis cliquez sur
            « Régénérer ».
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          <Button variant="outline" className="h-auto justify-start py-3" onClick={() => onAller(lienPlanning)}>
            <CalendarDays className="h-4 w-4 mr-2 shrink-0" />
            <span className="text-left">
              <span className="block font-medium">Planning du mois</span>
              <span className="block text-xs text-muted-foreground">Heures, absences, congés</span>
            </span>
            <ExternalLink className="h-3 w-3 ml-auto" />
          </Button>
          <Button variant="outline" className="h-auto justify-start py-3" onClick={() => onAller(lienFiche)}>
            <UserRound className="h-4 w-4 mr-2 shrink-0" />
            <span className="text-left">
              <span className="block font-medium">Fiche du salarié</span>
              <span className="block text-xs text-muted-foreground">Salaire, horaire, primes fixes</span>
            </span>
            <ExternalLink className="h-3 w-3 ml-auto" />
          </Button>
          <Button
            variant="outline"
            className="h-auto justify-start py-3"
            data-testid="corriger-les-variables"
            onClick={() => onAller(lienSaisies)}
          >
            <SlidersHorizontal className="h-4 w-4 mr-2 shrink-0" />
            <span className="text-left">
              <span className="block font-medium">Saisies du mois</span>
              <span className="block text-xs text-muted-foreground">Acomptes, frais, autres variables</span>
            </span>
            <ExternalLink className="h-3 w-3 ml-auto" />
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
