/**
 * Corriger une ligne du bulletin (théorème de la correction à la main, étape 2).
 *
 * Toute ligne calculée par Martine se corrige ici, par ce que la règle 3
 * permet : sa base ou son taux quand elle en porte (le montant suit au centime,
 * le serveur le recalcule), son montant sinon, le taux du mois pour l'impôt. La
 * correction est une variable du mois : à l'enregistrement, le bulletin est
 * recalculé en entier, et elle passe dans le net, les cumuls, la DSN et les
 * exports. Les codes et la règle viennent du serveur, jamais d'un calcul ici.
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PencilLine, Trash2, TriangleAlert, Undo2 } from 'lucide-react';

import { getLignesCorrigeables, type LigneCorrigeable } from '@/api/payslips';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  aideDeLaCorrection,
  apercuDuMontant,
  champsDeLaLigne,
  correctionDeLigne,
  type ChampCorrigeable,
  type EtatCorrections,
  eurosFr,
  formulaireDeLaVersion,
  type FormulaireDeLigne,
  formulaireVide,
  libelleDeLOption,
  resumeDeLaCorrection,
  resumeDeLaCorrectionAEnregistrer,
} from '@/features/payroll/utils/correctionsBulletin';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';

const BLOCS: Array<{ bloc: LigneCorrigeable['bloc']; titre: string }> = [
  { bloc: 'brut', titre: 'Rémunération' },
  { bloc: 'cotisations', titre: 'Cotisations' },
  { bloc: 'impot', titre: 'Impôt' },
];

interface Props {
  payslipId: string;
  /** `updated_at` du bulletin : la carte relit ses lignes après chaque enregistrement. */
  version: string | null;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
}

export default function CorrigerUneLigneCard({ payslipId, version, etat, onChange, disabled }: Props) {
  const companyId = useActiveCompanyId();
  const query = useQuery({
    queryKey: queryKeys.lignesCorrigeables(companyId, payslipId, version),
    queryFn: () => getLignesCorrigeables(payslipId, companyId),
    enabled: Boolean(companyId && payslipId),
    staleTime: 30_000,
  });
  // Le formulaire est attaché à la version du bulletin : après un
  // enregistrement, il revient à zéro.
  const [formulaire, setFormulaire] = useState<FormulaireDeLigne>(() => formulaireVide(version));
  const { code, cle, valeur, motif, reporterDe } = formulaireDeLaVersion(formulaire, version);
  const remplir = (changement: Partial<FormulaireDeLigne>) =>
    setFormulaire({ ...formulaireDeLaVersion(formulaire, version), ...changement });

  const lignes = query.data?.lignes ?? [];
  const enAttente = query.data?.en_attente ?? [];
  const corrigees = lignes.filter((l) => l.correction?.saisie_id);
  const retirees = new Set(etat.correctionsRetirees);
  const ligne = lignes.find((l) => l.code === code && l.mode);
  const champs = ligne ? champsDeLaLigne(ligne) : [];
  const champ = champs.find((c) => c.cle === cle) ?? champs[0];
  const nombre = Number.parseFloat(valeur.replace(',', '.'));
  const apercu = ligne && champ ? apercuDuMontant(ligne, champ.cle, nombre) : null;
  const saisieDeLaLigne = ligne?.correction?.saisie_id ? String(ligne.correction.saisie_id) : null;
  const dejaCorrigee = saisieDeLaLigne !== null && !retirees.has(saisieDeLaLigne);
  const aide = aideDeLaCorrection(valeur, motif);
  const pret = !!ligne && !!champ && aide === null && !dejaCorrigee;

  const basculer = (saisieId: string) =>
    onChange({
      ...etat,
      correctionsRetirees: retirees.has(saisieId)
        ? etat.correctionsRetirees.filter((id) => id !== saisieId)
        : [...etat.correctionsRetirees, saisieId],
    });

  const ajouter = () => {
    if (!pret || !ligne || !champ) return;
    const aRetirer = reporterDe && !retirees.has(reporterDe) ? [reporterDe] : [];
    onChange({
      ...etat,
      correctionsAjoutees: [...etat.correctionsAjoutees, correctionDeLigne(ligne, champ.cle, nombre, motif)],
      correctionsRetirees: [...etat.correctionsRetirees, ...aRetirer],
    });
    setFormulaire(formulaireVide(version));
  };

  return (
    <Card data-testid="corriger-une-ligne">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <PencilLine className="h-5 w-5" />
          Corriger une ligne
        </CardTitle>
        <CardDescription>
          Une ligne fausse ? Choisissez-la, corrigez sa base ou son taux (son montant si elle n’en a pas) et écrivez le
          motif. Le montant suit au centime. À l’enregistrement, le bulletin est recalculé en entier : net, cumuls, DSN
          et exports suivent.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {query.isLoading ? <p className="text-sm text-muted-foreground">Lecture des lignes du bulletin…</p> : null}
        {query.isError ? (
          <p className="text-sm text-destructive">Les lignes du bulletin n’ont pas pu être lues. Rechargez la page.</p>
        ) : null}

        {enAttente.length > 0 ? (
          <Alert variant="destructive" data-testid="corrections-en-attente">
            <TriangleAlert className="h-4 w-4" />
            <AlertDescription className="space-y-2">
              <p>
                Ces corrections ne trouvent plus leur ligne. Le bulletin ne peut pas être validé tant qu’elles ne sont
                pas retirées ou reportées sur une autre ligne.
              </p>
              {enAttente.map((attente) => {
                const id = String(attente.saisie_id ?? '');
                return (
                  <div key={id || attente.ligne} className="flex flex-wrap items-center justify-between gap-2">
                    <span className={retirees.has(id) ? 'line-through' : ''}>
                      {attente.libelle} — {attente.motif} ({attente.raison})
                    </span>
                    {id && !disabled ? (
                      <span className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => basculer(id)}>
                          {retirees.has(id) ? 'Garder' : 'Retirer'}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => remplir({ reporterDe: id, motif: attente.motif, code: '', cle: '', valeur: '' })}
                        >
                          Reporter sur une autre ligne
                        </Button>
                      </span>
                    ) : null}
                  </div>
                );
              })}
            </AlertDescription>
          </Alert>
        ) : null}

        {corrigees.map((l) => {
          const id = String(l.correction?.saisie_id);
          return (
            <div key={id} className="flex items-center justify-between rounded-md border p-3 text-sm">
              <div className={retirees.has(id) ? 'line-through text-muted-foreground' : ''}>
                <div className="font-medium">{l.libelle}</div>
                <div className="text-xs text-muted-foreground">
                  {resumeDeLaCorrection(l)} — {l.correction?.motif}
                </div>
              </div>
              {disabled ? null : (
                <Button variant="ghost" size="sm" onClick={() => basculer(id)}>
                  {retirees.has(id) ? (
                    <>
                      <Undo2 className="h-4 w-4 mr-1" /> Garder
                    </>
                  ) : (
                    <>
                      <Trash2 className="h-4 w-4 mr-1" /> Retirer
                    </>
                  )}
                </Button>
              )}
            </div>
          );
        })}

        {etat.correctionsAjoutees.map((c, index) => (
          <div
            key={`correction-${index}`}
            className="flex items-center justify-between rounded-md border border-dashed p-3 text-sm"
          >
            <div>
              <div className="font-medium">{c.libelle} (à enregistrer)</div>
              <div className="text-xs text-muted-foreground">
                {resumeDeLaCorrectionAEnregistrer(c, lignes.find((l) => l.code === c.ligne))} — {c.motif}
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              disabled={disabled}
              onClick={() =>
                onChange({ ...etat, correctionsAjoutees: etat.correctionsAjoutees.filter((_, i) => i !== index) })
              }
            >
              <Trash2 className="h-4 w-4 mr-1" /> Annuler
            </Button>
          </div>
        ))}

        {!disabled && lignes.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="ligne-a-corriger">
                Ligne{reporterDe ? ' (report de la correction en attente)' : ''}
              </Label>
              <select
                id="ligne-a-corriger"
                className="w-full rounded-md border px-2 py-2 text-sm"
                value={code}
                onChange={(e) => remplir({ code: e.target.value, cle: '', valeur: '' })}
              >
                <option value="">Choisissez une ligne…</option>
                {BLOCS.map(({ bloc, titre }) => (
                  <optgroup key={bloc} label={titre}>
                    {lignes
                      .filter((l) => l.bloc === bloc && l.code)
                      .map((l) => (
                        <option key={String(l.code)} value={String(l.code)} disabled={!l.mode} title={l.raison ?? undefined}>
                          {libelleDeLOption(l)}
                        </option>
                      ))}
                  </optgroup>
                ))}
              </select>
              {dejaCorrigee ? (
                <p className="text-xs text-destructive">
                  Cette ligne est déjà corrigée : retirez sa correction ci-dessus pour la refaire.
                </p>
              ) : null}
            </div>
            {ligne && champ ? (
              <>
                <div className="space-y-1">
                  <Label htmlFor="champ-a-corriger">Ce que vous corrigez</Label>
                  <select
                    id="champ-a-corriger"
                    className="w-full rounded-md border px-2 py-2 text-sm"
                    value={champ.cle}
                    onChange={(e) => remplir({ cle: e.target.value as ChampCorrigeable })}
                  >
                    {champs.map((c) => (
                      <option key={c.cle} value={c.cle}>
                        {c.libelle}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="valeur-corrigee">
                    Valeur voulue{champ.valeur !== null ? ` (Martine : ${String(champ.valeur).replace('.', ',')})` : ''}
                  </Label>
                  <Input
                    id="valeur-corrigee"
                    inputMode="decimal"
                    value={valeur}
                    aria-invalid={aide?.champ === 'valeur'}
                    onChange={(e) => remplir({ valeur: e.target.value })}
                  />
                  {aide?.champ === 'valeur' ? <p className="text-xs text-destructive">{aide.message}</p> : null}
                </div>
                <div className="space-y-1 sm:col-span-2">
                  <Label htmlFor="motif-correction">Motif (obligatoire)</Label>
                  <Input
                    id="motif-correction"
                    maxLength={300}
                    value={motif}
                    aria-invalid={aide?.champ === 'motif'}
                    onChange={(e) => remplir({ motif: e.target.value })}
                  />
                  {aide?.champ === 'motif' ? (
                    <p className="text-xs text-destructive" data-testid="motif-trop-court">
                      {aide.message}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
                  <Button variant="outline" disabled={!pret} onClick={ajouter} data-testid="ajouter-correction-ligne">
                    Ajouter la correction
                  </Button>
                  {apercu !== null ? (
                    <span className="text-sm text-muted-foreground">Montant après correction : {eurosFr(apercu)}</span>
                  ) : null}
                  {aide?.champ === 'bouton' && !dejaCorrigee ? (
                    <span className="text-xs text-muted-foreground">{aide.message}</span>
                  ) : null}
                </div>
              </>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
