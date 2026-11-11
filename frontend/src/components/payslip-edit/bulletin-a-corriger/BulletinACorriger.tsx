/**
 * L'onglet « Corriger » : le bulletin lui-même, corrigeable ligne par ligne
 * (design du 11/11/2026, retours de Lyon). Chaque correction reste une
 * variable du mois ; « Appliquer » (barre du bas) recalcule tout.
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ExternalLink, Lock, TriangleAlert, X } from 'lucide-react';

import { getLignesCorrigeables, type LigneCorrigeable } from '@/api/payslips';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  type DemandeDeCorrection,
  type EtatCorrections,
  eurosFr,
  type SaisieApresCalcul,
} from '@/features/payroll/utils/correctionsBulletin';
import {
  autresMontantsDuNet,
  correctionEnAttente,
  cotisationsAOuvrir,
  estRetiree,
  estSurLeNet,
  etapeEnCours,
  nombreDeChangements,
  origineDeLaLigne,
  primeDeLaLigne,
  type StatutDeLigne,
  suiviDesLignes,
} from '@/features/payroll/utils/bulletinACorriger';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';
import AjouterUneLigne from './AjouterUneLigne';
import BandeauEtapes from './BandeauEtapes';
import LigneDePrime from './LigneDePrime';
import LigneDuBulletin, { type ReportDeCorrection } from './LigneDuBulletin';
import LignesAjoutees from './LignesAjoutees';

interface Props {
  payslipId: string;
  version: string | null;
  payslipData: unknown;
  initial: EtatCorrections;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
  employeeId: string;
  year: number;
  month: number;
  lienPlanning: string;
  lienFiche: string;
  lienSaisies: string;
  forfaitJours?: boolean;
  tempsPartiel?: boolean;
  demande?: DemandeDeCorrection | null;
  /** La demande de l'onglet « Bulletin » est consommée : elle ne se rouvre plus au remontage. */
  onDemandeTraitee?: () => void;
  /** Le nombre de lignes ouvertes avec une valeur tapée et sans motif (dit dans la barre du bas). */
  onLignesSansMotif?: (nombre: number) => void;
  /** Pourquoi le bulletin ne se corrige pas, quand il est verrouillé. */
  raisonDuVerrou?: string | null;
  saisiesApresCalcul?: SaisieApresCalcul[];
  onAller: (lien: string) => void;
}

const SOURCE_DES_PRIMES = '« Primes du mois »';

function netAPayer(payslipData: unknown): number | null {
  const valeur = (payslipData as { net_a_payer?: unknown } | null)?.net_a_payer;
  return typeof valeur === 'number' ? valeur : null;
}

function Titre({ children }: { children: ReactNode }) {
  return <div className="bg-muted px-3 py-1.5 text-xs font-semibold text-muted-foreground">{children}</div>;
}

export default function BulletinACorriger(props: Props) {
  const { payslipId, version, payslipData, initial, etat, onChange, disabled, demande, onAller, onLignesSansMotif } = props;
  const companyId = useActiveCompanyId();
  const query = useQuery({
    queryKey: queryKeys.lignesCorrigeables(companyId, payslipId, version),
    queryFn: () => getLignesCorrigeables(payslipId, companyId),
    enabled: Boolean(companyId && payslipId),
    staleTime: 30_000,
  });
  // Les lignes ouvertes, et celles qui attendent leur motif. Le composant est
  // remonté à chaque nouvelle version du bulletin et à « Tout annuler » : tout repart fermé.
  const [statuts, setStatuts] = useState<ReadonlyMap<string, StatutDeLigne>>(new Map());
  const surEdition = useCallback(
    (code: string, statut: StatutDeLigne | null) =>
      setStatuts((avant) => {
        if ((avant.get(code) ?? null) === statut) return avant;
        const apres = new Map(avant);
        if (statut) apres.set(code, statut);
        else apres.delete(code);
        return apres;
      }),
    []
  );
  // « Reporter sur une autre ligne » : la correction non placée attend le crayon de la bonne ligne.
  const [report, setReport] = useState<ReportDeCorrection | null>(null);

  const lignes = (query.data?.lignes ?? []).filter((l) => l.code);
  const enAttente = query.data?.en_attente ?? [];
  const changements = nombreDeChangements(initial, etat);
  const suivi = suiviDesLignes(statuts, etat);
  useEffect(() => {
    onLignesSansMotif?.(suivi.sansMotif);
  }, [suivi.sansMotif, onLignesSansMotif]);
  useEffect(() => () => onLignesSansMotif?.(0), [onLignesSansMotif]);
  const lienDe = (ligne: LigneCorrigeable) => {
    const origine = origineDeLaLigne(ligne);
    if (origine === 'planning') return { texte: 'Vient du planning · ouvrir le planning du mois', onOuvrir: () => onAller(props.lienPlanning) };
    if (origine === 'fiche') return { texte: 'Vient de la fiche · ouvrir la fiche', onOuvrir: () => onAller(props.lienFiche) };
    return null;
  };
  const ligneDe = (ligne: LigneCorrigeable) => {
    const prime = primeDeLaLigne(etat, ligne);
    return prime ? (
      <LigneDePrime key={ligne.code} prime={prime} etat={etat} onChange={onChange} disabled={disabled} />
    ) : (
      <LigneDuBulletin
        key={ligne.code}
        ligne={ligne}
        etat={etat}
        onChange={onChange}
        disabled={disabled}
        lienSource={lienDe(ligne)}
        demande={demande}
        onDemandeTraitee={props.onDemandeTraitee}
        onEdition={surEdition}
        report={report}
        onReportPris={() => setReport(null)}
      />
    );
  };
  const remuneration = lignes.filter((l) => l.bloc === 'brut');
  const cotisations = lignes.filter((l) => l.bloc === 'cotisations');
  const impot = lignes.filter((l) => l.bloc === 'impot');
  const primesDuNet = etat.primes.filter(estSurLeNet);
  const montantsDuNet = autresMontantsDuNet(query.data?.a_la_source ?? [], initial);
  const nbChangementsCotisations = cotisations.filter((l) => correctionEnAttente(etat, l.code) || estRetiree(etat, l)).length;
  // Le bloc replié s'ouvre par le code, jamais ne se referme par lui : piloter
  // l'attribut `open` le refermait pendant la saisie.
  const blocCotisations = useRef<HTMLDetailsElement>(null);
  const ouvrirCotisations = cotisationsAOuvrir(cotisations, etat, statuts, demande);
  useEffect(() => {
    if (ouvrirCotisations && blocCotisations.current) blocCotisations.current.open = true;
  }, [ouvrirCotisations]);

  return (
    <div className="space-y-4" data-testid="bulletin-a-corriger">
      {disabled ? (
        <Alert data-testid="verrou-corriger">
          <Lock className="h-4 w-4" />
          <AlertDescription>
            {props.raisonDuVerrou?.trim()
              ? 'Ce bulletin ne se corrige pas pour l’instant : la raison est affichée en haut de la page.'
              : 'Ce bulletin ne se corrige pas pour l’instant.'}
          </AlertDescription>
        </Alert>
      ) : (
        <BandeauEtapes etape={etapeEnCours(suivi.enEdition > 0, changements)} />
      )}

      {enAttente.length > 0 ? (
        <Alert variant="destructive" data-testid="corrections-en-attente">
          <TriangleAlert className="h-4 w-4" />
          <AlertDescription className="space-y-2">
            <p>
              Ces corrections ne sont plus sur le bulletin. Il ne peut pas être validé tant qu’elles ne sont pas
              retirées ou reportées sur une autre ligne.
            </p>
            {enAttente.map((attente) => {
              const id = String(attente.saisie_id ?? '');
              const retiree = etat.correctionsRetirees.includes(id);
              const reportee = report?.id === id;
              return (
                <div key={id || attente.ligne} className="flex flex-wrap items-center justify-between gap-2">
                  <span className={retiree ? 'line-through' : ''}>
                    {attente.libelle} — {attente.motif} ({attente.raison})
                  </span>
                  {id && !disabled ? (
                    <span className="flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          onChange({
                            ...etat,
                            correctionsRetirees: retiree
                              ? etat.correctionsRetirees.filter((x) => x !== id)
                              : [...etat.correctionsRetirees, id],
                          })
                        }
                      >
                        {retiree ? 'Garder' : 'Retirer'}
                      </Button>
                      {!retiree && !reportee ? (
                        <Button
                          variant="outline"
                          size="sm"
                          data-testid={`reporter-${id}`}
                          onClick={() => setReport({ id, motif: attente.motif, libelle: attente.libelle })}
                        >
                          Reporter sur une autre ligne
                        </Button>
                      ) : null}
                    </span>
                  ) : null}
                  {reportee ? (
                    <div className="flex basis-full items-center justify-between gap-2 rounded-md bg-background/60 px-2 py-1" data-testid="report-en-cours">
                      <span>Cliquez le crayon de la bonne ligne : son motif sera repris, et cette correction remplacée.</span>
                      <Button variant="ghost" size="sm" aria-label="Abandonner le report" onClick={() => setReport(null)}>
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </AlertDescription>
        </Alert>
      ) : null}

      {props.saisiesApresCalcul && props.saisiesApresCalcul.length > 0 ? (
        <Alert data-testid="saisies-apres-calcul">
          <AlertDescription>
            Saisies du mois enregistrées après le calcul, pas encore sur le bulletin :{' '}
            {props.saisiesApresCalcul.map((s) => `${s.libelle} (${eurosFr(s.montant)})`).join(', ')}. « Appliquer » ou « Régénérer » les y prend.
          </AlertDescription>
        </Alert>
      ) : null}

      {query.isLoading ? <p className="text-sm text-muted-foreground">Lecture des lignes du bulletin…</p> : null}
      {query.isError ? <p className="text-sm text-destructive">Les lignes du bulletin n’ont pas pu être lues. Rechargez la page.</p> : null}

      <div className="overflow-hidden rounded-lg border bg-background">
        <div data-testid="bloc-remuneration">
          <Titre>Rémunération</Titre>
          {remuneration.map(ligneDe)}
        </div>
        <LignesAjoutees initial={initial} etat={etat} onChange={onChange} disabled={disabled} />
        {primesDuNet.length > 0 || montantsDuNet.length > 0 ? (
          <div data-testid="bloc-sur-le-net">
            <Titre>Sur le net</Titre>
            {primesDuNet.map((p) => (
              <LigneDePrime key={p.saisieId} prime={p} etat={etat} onChange={onChange} disabled={disabled} />
            ))}
            {montantsDuNet.map((b, i) => (
              <div key={`${b.libelle}-${b.source}-${i}`} className="flex items-center justify-between border-b px-3 py-2 text-sm">
                <div>
                  <div className="font-medium">{b.libelle}</div>
                  {b.source.startsWith(SOURCE_DES_PRIMES) ? (
                    <div className="text-xs text-muted-foreground">
                      Prime fixe : se corrige sur la fiche du salarié{' '}
                      <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => onAller(props.lienFiche)}>
                        Ouvrir la fiche
                      </Button>
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground">Se corrige dans {b.source}</div>
                  )}
                </div>
                <span className="tabular-nums">{b.montant != null ? eurosFr(b.montant) : ''}</span>
              </div>
            ))}
          </div>
        ) : null}
        {cotisations.length > 0 ? (
          <details ref={blocCotisations} data-testid="bloc-cotisations">
            <summary className="cursor-pointer bg-muted px-3 py-1.5 text-xs font-semibold text-muted-foreground">
              Cotisations ({cotisations.length} lignes) · elles se recalculent seules : ouvrez seulement si une cotisation précise est fausse
              {nbChangementsCotisations > 0 ? ` · ${nbChangementsCotisations} changement${nbChangementsCotisations > 1 ? 's' : ''} à appliquer` : ''}
            </summary>
            {cotisations.map(ligneDe)}
          </details>
        ) : null}
        {impot.length > 0 ? (
          <div>
            <Titre>Impôt</Titre>
            {impot.map(ligneDe)}
          </div>
        ) : null}
        <div className="flex items-center justify-between bg-muted/60 px-3 py-2 font-bold" data-testid="net-a-payer">
          <span>Net à payer</span>
          <span className="tabular-nums">{netAPayer(payslipData) != null ? eurosFr(netAPayer(payslipData)!) : '—'}</span>
        </div>
        <AjouterUneLigne
          payslipData={payslipData}
          etat={etat}
          onChange={onChange}
          disabled={disabled}
          forfaitJours={props.forfaitJours}
          tempsPartiel={props.tempsPartiel}
          employeeId={props.employeeId}
          year={props.year}
          month={props.month}
          demande={demande}
          onDemandeTraitee={props.onDemandeTraitee}
        />
      </div>

      <div className="flex flex-wrap gap-x-4">
        <Button
          variant="link"
          className="px-0"
          data-testid="corriger-les-variables"
          onClick={() => onAller(props.lienSaisies)}
        >
          Acomptes, frais et autres saisies du mois <ExternalLink className="ml-1 h-3 w-3" />
        </Button>
        <Button variant="link" className="px-0" onClick={() => onAller(props.lienPlanning)}>
          Planning du mois <ExternalLink className="ml-1 h-3 w-3" />
        </Button>
        <Button variant="link" className="px-0" onClick={() => onAller(props.lienFiche)}>
          Fiche du salarié <ExternalLink className="ml-1 h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}
