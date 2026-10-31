import { useEffect, useState, type ReactNode } from 'react';
import { Loader2, Save } from 'lucide-react';
import type { CompanyDetails, DatePaiement } from '@/api/company';
import { patchCompanyDetails } from '@/api/company';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { getUserErrorMessage } from '@/lib/errorMessages';
import {
  DESCRIPTIONS_REGIME_PERIODE_PAIE,
  LIBELLES_REGIME_PERIODE_PAIE,
  PAIRE_AVANT_DERNIER_VENDREDI,
  PAIRE_MOIS_CIVIL,
  formatJourDeFin,
  formatOccurrence,
  regimePeriodePaie,
  type RegimePeriodePaie,
} from '@/features/company/lib/periodePaie';
import {
  DESCRIPTIONS_DATE_PAIEMENT,
  LIBELLES_DATE_PAIEMENT,
  MISE_A_DISPOSITION_DES_LA_VALIDATION,
  MISE_A_DISPOSITION_JOUR_MAX,
  avertissementJourSolidarite,
  champsNonRelus,
  construireMiseAJour,
  libelleMiseADisposition,
  messageApresEnregistrement,
  repliEffectif,
  saisieInitiale,
  type ErreursParametresPaie,
  type SaisieParametresPaie,
} from '@/features/company/lib/parametresPaie';
import { useSurchargesPeriodeVariables } from '@/features/payroll/hooks/usePeriodeVariables';
import { lireTauxSaisi, tauxEnSaisie } from '../lib/tauxSociete';

type Erreurs = ErreursParametresPaie & { tauxAtMp?: string };

/** Dès la validation, puis le 1er au 28 du mois suivant. */
const JOURS_MISE_A_DISPOSITION = Array.from(
  { length: MISE_A_DISPOSITION_JOUR_MAX + 1 },
  (_, jour) => MISE_A_DISPOSITION_DES_LA_VALIDATION + jour,
);

function Aide({ children }: { children: ReactNode }) {
  return <p className="text-xs text-muted-foreground">{children}</p>;
}

function ErreurChamp({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} role="alert" className="text-xs font-medium text-destructive">
      {message}
    </p>
  );
}

export function CompanyPayrollParamsEditCard({
  company,
  canEdit,
  onSaved,
}: {
  company: CompanyDetails;
  canEdit: boolean;
  onSaved?: () => void;
}) {
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);
  // Dernière lecture connue de la société : la fiche, puis la relecture qui
  // suit chaque enregistrement. Les champs repartent toujours de là.
  const [reference, setReference] = useState<CompanyDetails>(company);
  const [tauxAtMp, setTauxAtMp] = useState(
    tauxEnSaisie(company.taux_at_mp),
  );
  const regimeInitial = regimePeriodePaie(
    reference.paie_jour_de_fin,
    reference.paie_occurrence,
  );
  const [regime, setRegime] = useState<RegimePeriodePaie>(regimeInitial);
  const [saisie, setSaisie] = useState<SaisieParametresPaie>(() => saisieInitiale(company));
  const [erreurs, setErreurs] = useState<Erreurs>({});
  // Le régime affiché mentirait s'il taisait les mois que la gestionnaire de
  // paie a arrêtés à une autre date.
  const anneeCourante = new Date().getFullYear();
  const { data: surcharges } = useSurchargesPeriodeVariables(anneeCourante);

  const repartirDe = (societe: CompanyDetails) => {
    setReference(societe);
    setTauxAtMp(tauxEnSaisie(societe.taux_at_mp));
    setRegime(regimePeriodePaie(societe.paie_jour_de_fin, societe.paie_occurrence));
    setSaisie(saisieInitiale(societe));
    setErreurs({});
  };

  // La fiche relue (après enregistrement ou rechargement) remet les champs à jour.
  useEffect(() => {
    repartirDe(company);
  }, [company]);

  if (!canEdit) return null;

  const modifier = <K extends keyof SaisieParametresPaie>(champ: K, valeur: SaisieParametresPaie[K]) => {
    setSaisie((s) => ({ ...s, [champ]: valeur }));
    setErreurs((e) => ({ ...e, [champ]: undefined }));
  };

  const avertissementSolidarite = avertissementJourSolidarite(saisie.jourSolidarite, anneeCourante);

  const handleSave = async () => {
    const { corps, erreurs: erreursReglages } = construireMiseAJour(reference, saisie);
    const tauxAtMpLu = lireTauxSaisi(tauxAtMp);
    const nouvellesErreurs: Erreurs = { ...erreursReglages };
    if ('erreur' in tauxAtMpLu) {
      nouvellesErreurs.tauxAtMp = tauxAtMpLu.erreur;
    }
    setErreurs(nouvellesErreurs);
    if (Object.keys(nouvellesErreurs).length > 0) {
      toast({
        title: 'À corriger avant d’enregistrer',
        description: 'Le message sous le champ dit quoi changer.',
        variant: 'destructive',
      });
      return;
    }

    setSaving(true);
    try {
      const { company_data: relue } = await patchCompanyDetails({
        taux_at_mp: 'valeur' in tauxAtMpLu ? tauxAtMpLu.valeur : undefined,
        // Un régime « personnalisé » ou non choisi n'écrase jamais le couple
        // (jour_de_fin, occurrence) existant.
        ...(regime === 'avant_dernier_vendredi' ? PAIRE_AVANT_DERNIER_VENDREDI : {}),
        ...(regime === 'mois_civil' ? PAIRE_MOIS_CIVIL : {}),
        ...corps,
      });
      const nonRelus = champsNonRelus(corps, relue);
      if (nonRelus.length > 0) {
        toast({
          title: 'Enregistrement incomplet',
          description: `Non pris en compte : ${nonRelus.join(', ')}. Rechargez la page et réessayez ; si cela persiste, signalez-le.`,
          variant: 'destructive',
        });
      } else {
        const message = messageApresEnregistrement(reference, relue);
        toast({ title: message.titre, description: message.description });
      }
      repartirDe(relue);
      onSaved?.();
    } catch (error) {
      toast({
        title: 'Enregistrement impossible',
        description: getUserErrorMessage(error, 'Rien n’a été enregistré. Réessayez.'),
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-lg border border-dashed bg-muted/20 p-4 space-y-3">
      <p className="text-sm font-medium">Compléter les paramètres paie</p>
      <p className="text-xs text-muted-foreground">
        Ces champs peuvent aussi être préremplis par un import DSN. Saisie manuelle en filet de
        sécurité. Changer un de ces réglages fait passer les brouillons déjà calculés « À
        recalculer » (un bulletin validé n&apos;est pas touché), sauf le compte bancaire de la
        société, qui ne touche à aucun bulletin.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="taux-at-mp">Taux AT/MP (%)</Label>
          <Input
            id="taux-at-mp"
            inputMode="decimal"
            value={tauxAtMp}
            onChange={(e) => {
              setTauxAtMp(e.target.value);
              setErreurs((er) => ({ ...er, tauxAtMp: undefined }));
            }}
            placeholder="ex. 3.66"
            aria-invalid={Boolean(erreurs.tauxAtMp)}
            aria-describedby={erreurs.tauxAtMp ? 'taux-at-mp-erreur' : undefined}
          />
          <ErreurChamp id="taux-at-mp-erreur" message={erreurs.tauxAtMp} />
        </div>
        <div className="space-y-1">
          <Label>Arrêté de la période de paie</Label>
          <Select
            value={regime === 'non_defini' ? '' : regime}
            onValueChange={(v) => setRegime(v as RegimePeriodePaie)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Choisir un régime…" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="avant_dernier_vendredi">
                {LIBELLES_REGIME_PERIODE_PAIE.avant_dernier_vendredi}
              </SelectItem>
              <SelectItem value="mois_civil">
                {LIBELLES_REGIME_PERIODE_PAIE.mois_civil}
              </SelectItem>
              {regimeInitial === 'personnalise' ? (
                <SelectItem value="personnalise">
                  {LIBELLES_REGIME_PERIODE_PAIE.personnalise} —{' '}
                  {formatJourDeFin(reference.paie_jour_de_fin)},{' '}
                  {formatOccurrence(reference.paie_occurrence).toLowerCase()}
                </SelectItem>
              ) : null}
            </SelectContent>
          </Select>
          {regime !== 'non_defini' ? (
            <p className="text-xs text-muted-foreground">
              {DESCRIPTIONS_REGIME_PERIODE_PAIE[regime]}
            </p>
          ) : null}
          {surcharges && surcharges.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              Fenêtre corrigée à la main sur{' '}
              {surcharges.length === 1 ? 'le mois' : 'les mois'} de{' '}
              {surcharges
                .map((s) =>
                  new Date(anneeCourante, s.month - 1).toLocaleString('fr-FR', {
                    month: 'long',
                  }),
                )
                .join(', ')}
              .
            </p>
          ) : null}
        </div>

        <div className="space-y-1">
          <Label htmlFor="taux-assurance-chomage">
            Taux d&apos;assurance chômage notifié par l&apos;URSSAF (%)
          </Label>
          <Input
            id="taux-assurance-chomage"
            inputMode="decimal"
            value={saisie.tauxChomage}
            onChange={(e) => modifier('tauxChomage', e.target.value)}
            placeholder="vide = taux normal"
            aria-invalid={Boolean(erreurs.tauxChomage)}
            aria-describedby="taux-assurance-chomage-aide"
          />
          <p id="taux-assurance-chomage-aide" className="text-xs text-muted-foreground">
            Seulement si l&apos;URSSAF vous a notifié un taux bonus-malus. Ne s&apos;applique pas
            aux apprentis.
          </p>
          <ErreurChamp id="taux-assurance-chomage-erreur" message={erreurs.tauxChomage} />
        </div>

        <div className="space-y-1">
          <Label htmlFor="effectif-seuils">
            Effectif retenu pour les seuils en {anneeCourante}
          </Label>
          <Input
            id="effectif-seuils"
            inputMode="numeric"
            value={saisie.effectif}
            onChange={(e) => modifier('effectif', e.target.value)}
            placeholder="ex. 12"
            aria-invalid={Boolean(erreurs.effectif)}
            aria-describedby="effectif-seuils-aide"
          />
          <p id="effectif-seuils-aide" className="text-xs text-muted-foreground">
            Effectif moyen de {anneeCourante - 1}, tel que l&apos;Urssaf le communique (compte
            rendu des effectifs annuels). Sert aux seuils de 11, 20 et 50 salariés ; Martine ne
            le recompte pas.
          </p>
          {repliEffectif(reference, anneeCourante) && saisie.effectif.trim() === '' && (
            <p className="text-xs font-medium text-amber-700 dark:text-amber-400">
              {repliEffectif(reference, anneeCourante)}
            </p>
          )}
          <ErreurChamp id="effectif-seuils-erreur" message={erreurs.effectif} />
        </div>

        <div className="space-y-1">
          <Label>Date de paiement des salaires</Label>
          <Select
            value={saisie.datePaiement}
            onValueChange={(v) => modifier('datePaiement', v as DatePaiement)}
          >
            <SelectTrigger aria-label="Date de paiement des salaires">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="dernier_jour_du_mois">
                {LIBELLES_DATE_PAIEMENT.dernier_jour_du_mois}
              </SelectItem>
              <SelectItem value="arrete_des_variables">
                {LIBELLES_DATE_PAIEMENT.arrete_des_variables}
              </SelectItem>
            </SelectContent>
          </Select>
          <Aide>{DESCRIPTIONS_DATE_PAIEMENT[saisie.datePaiement]}</Aide>
        </div>

        <div className="space-y-1">
          <Label>Bulletins visibles par les salariés</Label>
          <Select value={saisie.miseADisposition} onValueChange={(v) => modifier('miseADisposition', v)}>
            <SelectTrigger aria-label="Bulletins visibles par les salariés">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {JOURS_MISE_A_DISPOSITION.map((jour) => (
                <SelectItem key={jour} value={String(jour)}>
                  {libelleMiseADisposition(jour)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Aide>
            Le salarié voit son bulletin validé à cette date, et en est prévenu ; celui de son départ,
            dès la validation. Dès qu&apos;il est visible, le bulletin ne se modifie plus : une erreur
            se corrige le mois suivant.
          </Aide>
        </div>

        <div className="space-y-1">
          <Label htmlFor="jour-solidarite">
            Journée de solidarité (date de l&apos;année en cours)
          </Label>
          <Input
            id="jour-solidarite"
            type="date"
            value={saisie.jourSolidarite}
            onChange={(e) => modifier('jourSolidarite', e.target.value)}
            aria-invalid={Boolean(erreurs.jourSolidarite)}
            aria-describedby="jour-solidarite-aide"
          />
          <p id="jour-solidarite-aide" className="text-xs text-muted-foreground">
            Le jour férié travaillé au titre de la solidarité. Vide : lundi de Pentecôte.
          </p>
          {avertissementSolidarite ? (
            <p className="text-xs font-medium text-amber-700">{avertissementSolidarite}</p>
          ) : null}
          <ErreurChamp id="jour-solidarite-erreur" message={erreurs.jourSolidarite} />
        </div>

        <fieldset className="space-y-2 sm:col-span-2">
          <legend className="text-sm font-medium">Compte bancaire de la société</legend>
          <Aide>
            Le compte qui débite les salaires : il figure comme donneur d&apos;ordre dans les
            fichiers de virement (salaires et acomptes). Sans lui, l&apos;aperçu du virement est
            bloqué. Videz les trois champs pour le retirer.
          </Aide>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="compte-iban">IBAN du compte</Label>
              <Input
                id="compte-iban"
                value={saisie.compteIban}
                onChange={(e) => modifier('compteIban', e.target.value)}
                placeholder="FR76 …"
                autoComplete="off"
                aria-invalid={Boolean(erreurs.compteIban)}
                aria-describedby={erreurs.compteIban ? 'compte-iban-erreur' : undefined}
              />
              <ErreurChamp id="compte-iban-erreur" message={erreurs.compteIban} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="compte-bic">BIC (facultatif)</Label>
              <Input
                id="compte-bic"
                value={saisie.compteBic}
                onChange={(e) => modifier('compteBic', e.target.value)}
                placeholder="BNPAFRPP"
                autoComplete="off"
                aria-invalid={Boolean(erreurs.compteBic)}
                aria-describedby={erreurs.compteBic ? 'compte-bic-erreur' : undefined}
              />
              <ErreurChamp id="compte-bic-erreur" message={erreurs.compteBic} />
            </div>
            <div className="space-y-1 sm:col-span-3">
              <Label htmlFor="compte-titulaire">Titulaire du compte</Label>
              <Input
                id="compte-titulaire"
                value={saisie.compteTitulaire}
                onChange={(e) => modifier('compteTitulaire', e.target.value)}
                placeholder="Vide : le nom de la société"
                maxLength={70}
                aria-invalid={Boolean(erreurs.compteTitulaire)}
                aria-describedby={erreurs.compteTitulaire ? 'compte-titulaire-erreur' : undefined}
              />
              <ErreurChamp id="compte-titulaire-erreur" message={erreurs.compteTitulaire} />
            </div>
          </div>
        </fieldset>
      </div>
      <Button type="button" size="sm" onClick={() => void handleSave()} disabled={saving}>
        {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
        Enregistrer
      </Button>
    </div>
  );
}
