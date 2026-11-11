/**
 * Une ligne calculée du bulletin, corrigeable en place (design du 11/11/2026).
 * La correction s'écrit dans l'état dès que la valeur et le motif sont bons :
 * rien d'autre à valider que « Appliquer », en bas de l'écran.
 */
import { useEffect, useRef, useState } from 'react';
import { ExternalLink, PencilLine, Trash2, Undo2, X } from 'lucide-react';

import type { LigneCorrigeable } from '@/api/payslips';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  aideDeLaCorrection,
  apercuDuMontant,
  avisSurLaLigne,
  CE_QUI_SUIT_LA_CORRECTION,
  type ChampCorrigeable,
  type DemandeDeCorrection,
  type EtatCorrections,
  eurosFr,
  resumeDeLaCorrection,
} from '@/features/payroll/utils/correctionsBulletin';
import {
  annulerLaCorrection,
  autresChamps,
  champPropose,
  correctionEnAttente,
  corrigerLaLigne,
  estRetiree,
  libelleDuChamp,
  MOTIFS_PROPOSES,
  type ReportsDeCorrections,
  remettre,
  retirer,
  retraitDeLaLigne,
  type StatutDeLigne,
  uniteDuChamp,
  valeurEnAttente,
} from '@/features/payroll/utils/bulletinACorriger';
import { lireNombre } from '@/lib/nombreSaisi';
import { cn } from '@/lib/utils';
import MotifEnPuces from './MotifEnPuces';

/** Une correction en attente (non placée) à reporter sur la ligne dont on ouvrira le crayon. */
export interface ReportDeCorrection {
  id: string;
  motif: string;
  libelle: string;
}

interface Props {
  ligne: LigneCorrigeable;
  etat: EtatCorrections;
  onChange: (etat: EtatCorrections) => void;
  disabled?: boolean;
  lienSource: { texte: string; onOuvrir: () => void } | null;
  demande?: DemandeDeCorrection | null;
  /** La demande de l'onglet « Bulletin » est consommée : elle ne se rouvre plus. */
  onDemandeTraitee?: () => void;
  /** La ligne dit si elle est ouverte, et si une valeur y attend son motif (null : fermée). */
  onEdition: (code: string, statut: StatutDeLigne | null) => void;
  report?: ReportDeCorrection | null;
  onReportPris?: () => void;
  /** Les reports posés (ligne → correction remplacée), gardés par la page : ils survivent au démontage de l'onglet. */
  reports?: ReportsDeCorrections;
  onLienDeReport?: (code: string, id: string | null) => void;
}

function montantAffiche(ligne: LigneCorrigeable): string {
  if (ligne.bloc === 'cotisations') {
    const parts = [
      ligne.montant_salarial ? `salarié ${eurosFr(ligne.montant_salarial)}` : null,
      ligne.montant_patronal ? `employeur ${eurosFr(ligne.montant_patronal)}` : null,
    ].filter(Boolean);
    return parts.join(' · ');
  }
  if (ligne.montant == null) return '';
  return `${ligne.retenue ? '−' : ''}${eurosFr(ligne.montant)}`;
}

/** La valeur de Martine en clair : deux décimales pour un montant en euros. */
function valeurDeMartine(valeur: number | null | undefined, unite: string): string {
  if (valeur == null) return '—';
  if (unite === '€') return valeur.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return String(valeur).replace('.', ',');
}

export default function LigneDuBulletin(props: Props) {
  const { ligne, etat, onChange, disabled, lienSource, demande, onEdition, report } = props;
  const reports = props.reports ?? {};
  const code = String(ligne.code ?? '');
  const enAttente = correctionEnAttente(etat, code);
  const retiree = estRetiree(etat, ligne);
  const retrait = retraitDeLaLigne(ligne, etat);
  const propose = champPropose(ligne);
  const [ouverte, setOuverte] = useState(false);
  const [cle, setCle] = useState<ChampCorrigeable | ''>('');
  const [texte, setTexte] = useState('');
  const [motif, setMotif] = useState('');
  const [motifRetrait, setMotifRetrait] = useState<string | null>(null);
  // La correction en attente (non placée) que cette ligne remplace, prise au crayon.
  const [reportDe, setReportDe] = useState<ReportDeCorrection | null>(null);
  // La correction déjà posée était retirée par la RH avant le crayon : ✕ la laisse retirée.
  const [garderRetiree, setGarderRetiree] = useState(false);
  const racine = useRef<HTMLDivElement>(null);
  const champDe = (k: ChampCorrigeable | '') => (k && [propose, ...autresChamps(ligne)].find((c) => c?.cle === k)) || propose;
  const champ = champDe(cle);

  const ouvrir = () => {
    // Une correction déjà en attente : on rouvre sur son champ, avec sa valeur.
    const dejaTapee = valeurEnAttente(enAttente);
    setOuverte(true);
    setCle(dejaTapee?.cle ?? '');
    setTexte(dejaTapee ? String(dejaTapee.valeur).replace('.', ',') : '');
    // Un report en cours : le motif de la correction reportée est repris.
    const repris = !enAttente && report ? report : null;
    setReportDe(repris);
    const posee = ligne.correction?.saisie_id ? String(ligne.correction.saisie_id) : null;
    setGarderRetiree(Boolean(posee && !enAttente && etat.correctionsRetirees.includes(posee)));
    setMotif(enAttente?.motif ?? repris?.motif ?? '');
  };
  const fermer = () => {
    setOuverte(false);
    setTexte('');
    setMotif('');
    setCle('');
    setReportDe(null);
    setGarderRetiree(false);
  };

  useEffect(() => {
    if (demande?.carte !== 'ligne' || demande.code !== code) return;
    if (propose && !disabled) {
      ouvrir();
      // Après l'ouverture du bloc replié des cotisations, sinon le défilement ne trouve rien.
      window.requestAnimationFrame(() => racine.current?.scrollIntoView?.({ behavior: 'smooth', block: 'center' }));
    }
    props.onDemandeTraitee?.();
    // Le jeton change à chaque clic venu de l'onglet « Bulletin ».
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demande?.jeton]);

  /** Chaque frappe met l'état à jour : une valeur et un motif valides font une correction en attente. */
  const ecrire = (nouveauTexte: string, nouveauMotif: string, nouvelleCle: ChampCorrigeable | '' = cle) => {
    setTexte(nouveauTexte);
    setMotif(nouveauMotif);
    const cible = champDe(nouvelleCle);
    const nombre = lireNombre(nouveauTexte);
    // Le report de la ligne : celui pris au crayon, sinon le lien gardé par la page.
    const reporteDe = reportDe?.id ?? reports[code] ?? null;
    const options = { reporteDe, reports, garderLaCorrectionPoseeRetiree: garderRetiree };
    if (cible && nombre !== null && aideDeLaCorrection(nouveauTexte, nouveauMotif) === null) {
      onChange(corrigerLaLigne(etat, ligne, cible.cle, nombre, nouveauMotif, options));
      if (reporteDe) props.onLienDeReport?.(code, reporteDe);
      if (reportDe && report?.id === reportDe.id) props.onReportPris?.();
    } else {
      // Le lien reste : retaper une valeur reprend le report ; ✕ le défait.
      onChange(annulerLaCorrection(etat, ligne, options));
    }
  };

  const retirerAvecMotif = (m: string) => {
    onChange(retirer(etat, ligne, m));
    setMotifRetrait(null);
  };

  const nombre = lireNombre(texte);
  const apercu = ouverte && champ && nombre !== null ? apercuDuMontant(ligne, champ.cle, nombre) : null;
  // Ligne refermée avec une correction en attente : le nouveau montant reste dit.
  const tapee = !ouverte && !retiree ? valeurEnAttente(enAttente) : null;
  const apercuEnAttente = tapee ? apercuDuMontant(ligne, tapee.cle, tapee.valeur) : null;
  const aide = ouverte ? aideDeLaCorrection(texte, motif) : null;
  // Une valeur tapée sans motif n'est pas en attente : dit en ambre, jamais en silence.
  const sansMotif = ouverte && nombre !== null && aide?.champ === 'bouton';
  const statut: StatutDeLigne | null = ouverte ? (sansMotif ? 'sans_motif' : 'edition') : motifRetrait !== null ? 'edition' : null;
  useEffect(() => {
    onEdition(code, statut);
  }, [code, statut, onEdition]);
  useEffect(() => () => onEdition(code, null), [code, onEdition]);
  const avis = ouverte ? avisSurLaLigne(ligne) : null;
  const dejaCorrigee = Boolean(ligne.correction?.saisie_id);
  const correctionRetiree = dejaCorrigee && etat.correctionsRetirees.includes(String(ligne.correction?.saisie_id));

  return (
    <div
      ref={racine}
      data-testid={`ligne-${code}`}
      data-motif-manquant={sansMotif ? 'oui' : undefined}
      className={cn(
        'flex flex-col gap-2 border-b px-3 py-2 text-sm sm:flex-row sm:items-start sm:justify-between',
        ouverte && !sansMotif && 'bg-blue-50 outline outline-2 -outline-offset-2 outline-blue-500 dark:bg-blue-950/30',
        sansMotif && 'bg-amber-50 outline outline-2 -outline-offset-2 outline-amber-500 dark:bg-amber-950/30',
        retiree && 'bg-red-50 dark:bg-red-950/20',
        !retiree && enAttente && !ouverte && 'bg-amber-50 dark:bg-amber-950/20'
      )}
    >
      <div className="min-w-0 flex-1 space-y-1">
        <div className={cn('font-medium', retiree && 'text-muted-foreground line-through')}>
          {ligne.libelle}
          {retiree ? (
            <span className="ml-2 rounded bg-red-100 px-1.5 text-xs font-semibold text-red-700 dark:bg-red-950/60 dark:text-red-300">
              Retirée
            </span>
          ) : null}
          {!retiree && enAttente ? (
            <span className="ml-2 rounded bg-amber-100 px-1.5 text-xs font-semibold text-amber-800 dark:bg-amber-950/60 dark:text-amber-200">
              À appliquer
            </span>
          ) : null}
          {sansMotif ? (
            <span className="ml-2 rounded bg-amber-100 px-1.5 text-xs font-semibold text-amber-800 dark:bg-amber-950/60 dark:text-amber-200">
              Motif manquant
            </span>
          ) : null}
        </div>
        {lienSource ? (
          <button type="button" className="text-xs text-muted-foreground underline-offset-2 hover:underline" onClick={lienSource.onOuvrir}>
            {lienSource.texte} <ExternalLink className="inline h-3 w-3" />
          </button>
        ) : null}
        {!ligne.mode && !retrait && ligne.raison ? <p className="text-xs text-muted-foreground">{ligne.raison}</p> : null}
        {dejaCorrigee ? (
          <p className={cn('text-xs text-muted-foreground', correctionRetiree && 'line-through')}>
            Corrigée : {resumeDeLaCorrection(ligne)} — {ligne.correction?.motif}
          </p>
        ) : null}
        {ligne.alerte ? <p className="text-xs text-destructive">{ligne.alerte}</p> : null}
        {retiree && enAttente ? <p className="text-xs text-muted-foreground">Motif : {enAttente.motif}</p> : null}

        {ouverte && champ ? (
          <div className="mt-2 space-y-3 rounded-md border bg-background p-3">
            {reportDe ? (
              <p className="text-xs text-muted-foreground" data-testid={`report-sur-${code}`}>
                Report de la correction « {reportDe.libelle} » : elle sera remplacée par celle-ci.
              </p>
            ) : reports[code] ? (
              <p className="text-xs text-muted-foreground" data-testid={`report-sur-${code}`}>
                Cette correction remplace une correction en attente qui ne trouvait plus sa ligne.
              </p>
            ) : null}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">
                Martine : {valeurDeMartine(champ.valeur, uniteDuChamp(ligne, champ.cle))} {uniteDuChamp(ligne, champ.cle)}
              </span>
              <span>· {libelleDuChamp(ligne, champ.cle)} :</span>
              <Input
                autoFocus
                data-testid={`valeur-${code}`}
                aria-label={libelleDuChamp(ligne, champ.cle)}
                inputMode="decimal"
                className="w-28 border-2 border-blue-500 text-right font-semibold"
                value={texte}
                aria-invalid={aide?.champ === 'valeur'}
                onChange={(e) => ecrire(e.target.value, motif)}
              />
              <span className="text-sm">{uniteDuChamp(ligne, champ.cle)}</span>
            </div>
            {autresChamps(ligne).length > 0 ? (
              <div className="flex flex-wrap gap-2 text-xs">
                {[propose, ...autresChamps(ligne)]
                  .filter((c) => c && c.cle !== champ.cle)
                  .map((c) => (
                    <button
                      key={c!.cle}
                      type="button"
                      className="text-blue-700 underline-offset-2 hover:underline dark:text-blue-300"
                      onClick={() => {
                        setCle(c!.cle);
                        ecrire('', motif, c!.cle);
                      }}
                    >
                      Corriger plutôt : {libelleDuChamp(ligne, c!.cle).toLowerCase()}
                    </button>
                  ))}
              </div>
            ) : null}
            {aide?.champ === 'valeur' ? <p className="text-xs text-destructive">{aide.message}</p> : null}
            <MotifEnPuces testId={`motif-${code}`} valeur={motif} onValeur={(m) => ecrire(texte, m)} />
            {aide?.champ === 'motif' ? <p className="text-xs text-destructive">{aide.message}</p> : null}
            {sansMotif ? (
              <p className="text-xs font-medium text-amber-800 dark:text-amber-200" data-testid={`aide-motif-${code}`}>
                Choisissez un motif : il est imprimé sur le bulletin. Sans motif, cette correction n’est pas appliquée.
              </p>
            ) : null}
            {avis ? (
              <p className="text-xs text-muted-foreground" data-testid="avis-sur-la-ligne">
                {avis}
              </p>
            ) : null}
            <p className="text-xs text-muted-foreground" data-testid="ce-qui-suit-la-correction">
              {CE_QUI_SUIT_LA_CORRECTION}
            </p>
          </div>
        ) : null}

        {motifRetrait !== null ? (
          <div className="mt-2 space-y-2 rounded-md border bg-background p-3">
            <MotifEnPuces
              testId={`motif-retrait-${code}`}
              valeur={motifRetrait}
              onValeur={(m) => {
                // Une puce retire tout de suite ; un motif libre attend le bouton « Retirer la ligne ».
                if (MOTIFS_PROPOSES.includes(m)) retirerAvecMotif(m);
                else setMotifRetrait(m);
              }}
            />
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                data-testid={`confirmer-retrait-${code}`}
                disabled={motifRetrait.trim().length < 3}
                onClick={() => retirerAvecMotif(motifRetrait.trim())}
              >
                Retirer la ligne
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setMotifRetrait(null)}>
                Annuler
              </Button>
            </div>
          </div>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:pl-3">
        <span className={cn('tabular-nums', retiree && 'text-muted-foreground line-through')}>
          {montantAffiche(ligne)}
          {apercu !== null ? (
            <span data-testid={`apercu-${code}`} className="ml-1 font-semibold">
              → {eurosFr(apercu)}
            </span>
          ) : apercuEnAttente !== null ? (
            <span data-testid={`apercu-${code}`} className="ml-1 font-semibold">
              → {eurosFr(apercuEnAttente)}
            </span>
          ) : null}
        </span>
        {disabled ? null : retiree ? (
          <Button
            variant="outline"
            size="sm"
            data-testid={`remettre-${code}`}
            onClick={() => {
              onChange(remettre(etat, ligne, { reports }));
              props.onLienDeReport?.(code, null);
              // Une valeur 0 tapée au crayon : l'éditeur se ferme avec la correction.
              if (ouverte) fermer();
            }}
          >
            <Undo2 className="mr-1 h-4 w-4" /> Remettre
          </Button>
        ) : ouverte ? (
          <Button
            variant="ghost"
            size="sm"
            aria-label="Annuler cette correction"
            onClick={() => {
              onChange(
                annulerLaCorrection(etat, ligne, {
                  reporteDe: reportDe?.id ?? reports[code] ?? null,
                  reports,
                  garderLaCorrectionPoseeRetiree: garderRetiree,
                })
              );
              props.onLienDeReport?.(code, null);
              fermer();
            }}
          >
            <X className="h-4 w-4" />
          </Button>
        ) : motifRetrait !== null ? null : (
          <>
            {propose ? (
              <Button variant="outline" size="sm" data-testid={`corriger-${code}`} aria-label={`Corriger ${ligne.libelle}`} onClick={ouvrir}>
                <PencilLine className="h-4 w-4" />
              </Button>
            ) : null}
            {retrait ? (
              <Button
                variant="outline"
                size="sm"
                className="text-red-700 dark:text-red-400"
                data-testid={`retirer-${code}`}
                aria-label={`Retirer ${ligne.libelle}`}
                onClick={() => {
                  if (retrait.type === 'montant_zero') setMotifRetrait('');
                  else onChange(retirer(etat, ligne, ''));
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            ) : null}
            {/* Une correction en attente remplace déjà celle du bulletin : la garder ferait refuser l'application. */}
            {dejaCorrigee && !enAttente ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  const id = String(ligne.correction?.saisie_id);
                  onChange({
                    ...etat,
                    correctionsRetirees: correctionRetiree
                      ? etat.correctionsRetirees.filter((x) => x !== id)
                      : [...etat.correctionsRetirees, id],
                  });
                }}
              >
                {correctionRetiree ? 'Garder la correction' : 'Remettre la valeur de Martine'}
              </Button>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
