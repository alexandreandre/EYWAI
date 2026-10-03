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
  avertissementJourSolidarite,
  champsNonRelus,
  construireMiseAJour,
  parametresOntChange,
  resumeParametresPaie,
  saisieInitiale,
  type ErreursParametresPaie,
  type SaisieParametresPaie,
} from '@/features/company/lib/parametresPaie';
import { useSurchargesPeriodeVariables } from '@/features/payroll/hooks/usePeriodeVariables';

type Erreurs = ErreursParametresPaie & { tauxAtMp?: string };

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
    company.taux_at_mp != null ? String(company.taux_at_mp) : '',
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
    setTauxAtMp(societe.taux_at_mp != null ? String(societe.taux_at_mp) : '');
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
    const tauxAtMpNormalise = tauxAtMp.trim().replace(',', '.');
    const nouvellesErreurs: Erreurs = { ...erreursReglages };
    if (tauxAtMpNormalise !== '' && !/^\d+(\.\d+)?$/.test(tauxAtMpNormalise)) {
      nouvellesErreurs.tauxAtMp = 'Indiquez un nombre, par exemple 3,66.';
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
        taux_at_mp: tauxAtMpNormalise === '' ? undefined : Number(tauxAtMpNormalise),
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
        const recalcul = parametresOntChange(reference, relue)
          ? ' Les bulletins déjà calculés passent « À recalculer ».'
          : '';
        toast({
          title: 'Paramètres paie enregistrés',
          description: `${resumeParametresPaie(relue)}.${recalcul}`,
        });
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
        sécurité. Changer un de ces réglages fait passer les bulletins déjà calculés « À
        recalculer ».
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
          <Label htmlFor="effectif-seuils">Effectif retenu pour les seuils</Label>
          <Input
            id="effectif-seuils"
            inputMode="numeric"
            value={saisie.effectif}
            onChange={(e) => modifier('effectif', e.target.value)}
            placeholder="ex. 19"
            aria-invalid={Boolean(erreurs.effectif)}
            aria-describedby="effectif-seuils-aide"
          />
          <p id="effectif-seuils-aide" className="text-xs text-muted-foreground">
            Effectif moyen de l&apos;année précédente. Sert aux seuils de 11, 20 et 50 salariés.
          </p>
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
      </div>
      <Button type="button" size="sm" onClick={() => void handleSave()} disabled={saving}>
        {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
        Enregistrer
      </Button>
    </div>
  );
}
