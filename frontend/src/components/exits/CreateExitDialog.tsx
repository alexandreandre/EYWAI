/**
 * Dialog pour créer un nouveau processus de sortie de salarié
 */

import { log } from '@/lib/logger';
import { useState, useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';
import {
  createEmployeeExit,
  ExitType,
  CreateEmployeeExitRequest,
  getExitEligibleEmployees,
  getNoticePeriodPreview,
  NoticePeriodPreview,
  SimpleEmployee,
} from '@/api/employeeExits';
import { messageDepartCree } from '@/features/employee-exits/utils/messageDepartCree';
import {
  OPTIONS_PREAVIS,
  PREAVIS_PAR_DEFAUT,
  libelleSourcePreavis,
  preavisASaisir,
  typePreavisApresApercu,
  typePreavisApresSaisie,
  type TypePreavis,
} from '@/features/employee-exits/utils/preavis';
import {
  INITIATIVE_RETRAITE_PAR_DEFAUT,
  OPTIONS_INITIATIVE_RETRAITE,
  type InitiativeRetraite,
} from '@/features/employee-exits/utils/retraite';
import {
  LIBELLE_INDEMNITE_CONVENTIONNELLE,
  aideIndemniteConventionnelle,
  indemniteConventionnelleSaisissable,
} from '@/features/employee-exits/utils/indemniteConventionnelle';
import { lireMontantNegocie } from '@/features/employee-exits/utils/montantNegocie';
import {
  AIDE_PENSION_LIQUIDABLE,
  LIBELLE_PENSION_LIQUIDABLE,
} from '@/features/employee-exits/utils/pensionLiquidable';
import {
  AIDE_DELAI_PREVENANCE,
  OPTIONS_INITIATIVE_ESSAI,
  type InitiativeEssai,
} from '@/features/employee-exits/utils/periodeEssai';
import { AlertCircle, Info, Loader2 } from 'lucide-react';

interface CreateExitDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
  initialEmployeeId?: string;
  initialExitType?: ExitType;
  /** Dernier jour travaillé déjà connu (fin de contrat lue sur la fiche). */
  initialLastWorkingDay?: string;
}

export const CONTRAT_ABSENT_MESSAGE =
  "Le document du contrat de ce collaborateur n'est pas rangé dans Martine (la fiche peut porter son contrat) : le départ se crée quand même.";

export function CreateExitDialog({
  open,
  onOpenChange,
  onSuccess,
  initialEmployeeId,
  initialExitType,
  initialLastWorkingDay,
}: CreateExitDialogProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const companyId = useActiveCompanyId();
  const [loading, setLoading] = useState(false);
  const [loadingEmployees, setLoadingEmployees] = useState(false);
  const [loadingNoticePreview, setLoadingNoticePreview] = useState(false);
  const [noticePreview, setNoticePreview] = useState<NoticePeriodPreview | null>(null);
  const [noticePreviewError, setNoticePreviewError] = useState<string | null>(null);
  const [employees, setEmployees] = useState<SimpleEmployee[]>([]);
  const noticeManuallyEdited = useRef(false);

  // Form state
  const [employeeId, setEmployeeId] = useState<string>('');
  const [exitType, setExitType] = useState<ExitType>('demission');
  const [exitRequestDate, setExitRequestDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [lastWorkingDay, setLastWorkingDay] = useState<string>('');
  const [noticePeriodDays, setNoticePeriodDays] = useState<number>(0);
  const [isGrossMisconduct, setIsGrossMisconduct] = useState(false);
  const [noticeIndemnityType, setNoticeIndemnityType] = useState<TypePreavis>(PREAVIS_PAR_DEFAUT);
  const [exitReason, setExitReason] = useState<string>('');
  const [initiativeRetraite, setInitiativeRetraite] = useState<InitiativeRetraite>(
    INITIATIVE_RETRAITE_PAR_DEFAUT
  );
  const [indemniteConventionnelle, setIndemniteConventionnelle] = useState<string>('');
  const [pensionLiquidable, setPensionLiquidable] = useState(false);
  const [initiativeEssai, setInitiativeEssai] = useState<InitiativeEssai | ''>('');

  const selectedEmployee = employees.find((emp) => emp.id === employeeId);
  // Salarié présélectionné (bandeau de la Paie) absent de la liste : le dire,
  // plutôt qu'un choix vide sans explication.
  const [listeChargee, setListeChargee] = useState(false);
  const preselectionAbsente =
    open &&
    listeChargee &&
    Boolean(initialEmployeeId) &&
    !employees.some((emp) => emp.id === initialEmployeeId);

  const resetForm = () => {
    setListeChargee(false);
    setEmployeeId('');
    setExitType('demission');
    setExitRequestDate(new Date().toISOString().split('T')[0]);
    setLastWorkingDay('');
    setNoticePeriodDays(0);
    setIsGrossMisconduct(false);
    setNoticeIndemnityType(PREAVIS_PAR_DEFAUT);
    setExitReason('');
    setInitiativeRetraite(INITIATIVE_RETRAITE_PAR_DEFAUT);
    setIndemniteConventionnelle('');
    setPensionLiquidable(false);
    setInitiativeEssai('');
    setNoticePreview(null);
    setNoticePreviewError(null);
    noticeManuallyEdited.current = false;
  };

  useEffect(() => {
    if (open) {
      fetchEmployees();
      if (initialEmployeeId) {
        setEmployeeId(initialEmployeeId);
      }
      if (initialExitType) {
        handleExitTypeChange(initialExitType);
      }
      if (initialLastWorkingDay) {
        setLastWorkingDay(initialLastWorkingDay);
        // Fin de contrat déjà passée : la demande ne peut pas être postérieure
        // au dernier jour, sinon l'enregistrement est refusé.
        const aujourdHui = new Date().toISOString().split('T')[0];
        if (initialLastWorkingDay < aujourdHui) setExitRequestDate(initialLastWorkingDay);
      }
    } else {
      resetForm();
    }
  }, [open, initialEmployeeId, initialExitType, initialLastWorkingDay]);

  useEffect(() => {
    if (!open || !employeeId) {
      setNoticePreview(null);
      setNoticePreviewError(null);
      return;
    }

    let cancelled = false;

    const loadNoticePreview = async () => {
      setLoadingNoticePreview(true);
      setNoticePreviewError(null);
      try {
        const preview = await getNoticePeriodPreview({
          employee_id: employeeId,
          exit_type: exitType,
          reference_date: exitRequestDate,
          is_gross_misconduct: exitType === 'licenciement' ? isGrossMisconduct : false,
        });
        if (cancelled) return;

        setNoticePreview(preview);
        if (!noticeManuallyEdited.current) {
          setNoticePeriodDays(preview.notice_period_days);
          // Un préavis proposé est exécuté par défaut : jamais une indemnité
          // que la gestionnaire n'a pas choisie (L1234-5, [H1]).
          setNoticeIndemnityType((actuel) => typePreavisApresApercu(preview, actuel));
        }
      } catch (error: unknown) {
        if (cancelled) return;
        log.error('Erreur lors du calcul du préavis:', error);
        setNoticePreview(null);
        const detail =
          (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          'Impossible de calculer le préavis pour ce collaborateur';
        setNoticePreviewError(detail);
      } finally {
        if (!cancelled) {
          setLoadingNoticePreview(false);
        }
      }
    };

    loadNoticePreview();
    return () => {
      cancelled = true;
    };
  }, [employeeId, exitType, exitRequestDate, isGrossMisconduct, open]);

  const fetchEmployees = async () => {
    setLoadingEmployees(true);
    try {
      const eligibleEmployees = await getExitEligibleEmployees();
      setEmployees(eligibleEmployees);
      setListeChargee(true);
      // Présélection (bandeau de la Paie) : reposée une fois la liste là.
      if (initialEmployeeId && eligibleEmployees.some((emp) => emp.id === initialEmployeeId)) {
        setEmployeeId(initialEmployeeId);
      }
    } catch (error) {
      log.error('Erreur lors du chargement des employés:', error);
      toast({
        title: 'Erreur',
        description: 'Impossible de charger la liste des employés',
        variant: 'destructive',
      });
    } finally {
      setLoadingEmployees(false);
    }
  };

  const handleEmployeeChange = (value: string) => {
    // La liste déroulante renvoie une valeur vide quand la présélection arrive
    // avant ses options : on ne vide pas le choix pour autant (recette 02/10).
    if (!value) return;
    setEmployeeId(value);
    noticeManuallyEdited.current = false;
  };

  const handleExitTypeChange = (value: ExitType) => {
    setExitType(value);
    noticeManuallyEdited.current = false;
    if (value !== 'licenciement') {
      setIsGrossMisconduct(false);
    }
    if (!preavisASaisir(value)) {
      setNoticePeriodDays(0);
      setNoticeIndemnityType('not_applicable');
    }
  };

  const handleNoticePeriodChange = (value: number) => {
    noticeManuallyEdited.current = true;
    setNoticePeriodDays(value);
    setNoticeIndemnityType((actuel) => typePreavisApresSaisie(value, actuel));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!employeeId) {
      toast({
        title: 'Erreur',
        description: 'Veuillez sélectionner un employé',
        variant: 'destructive',
      });
      return;
    }

    if (!lastWorkingDay) {
      toast({
        title: 'Erreur',
        description: 'Veuillez indiquer le dernier jour de travail',
        variant: 'destructive',
      });
      return;
    }

    if (new Date(lastWorkingDay) < new Date(exitRequestDate)) {
      toast({
        title: 'Erreur',
        description: 'Le dernier jour de travail doit être postérieur ou égal à la date de demande',
        variant: 'destructive',
      });
      return;
    }

    if (exitType === 'fin_periode_essai' && !initiativeEssai) {
      toast({
        title: 'Erreur',
        description: "Indiquez qui rompt la période d'essai : le délai de prévenance en dépend.",
        variant: 'destructive',
      });
      return;
    }

    const conventionnelle = indemniteConventionnelleSaisissable(exitType)
      ? lireMontantNegocie(indemniteConventionnelle)
      : { valeur: null };
    if ('erreur' in conventionnelle) {
      toast({ title: 'Indemnité conventionnelle', description: conventionnelle.erreur, variant: 'destructive' });
      return;
    }

    setLoading(true);

    try {
      const data: CreateEmployeeExitRequest = {
        employee_id: employeeId,
        exit_type: exitType,
        exit_request_date: exitRequestDate,
        last_working_day: lastWorkingDay,
        notice_period_days: noticePeriodDays,
        is_gross_misconduct: isGrossMisconduct,
        notice_indemnity_type: noticeIndemnityType,
        exit_reason: exitReason || undefined,
        ...(exitType === 'depart_retraite' ? { retirement_initiator: initiativeRetraite } : {}),
        ...(conventionnelle.valeur !== null ? { indemnite_conventionnelle: conventionnelle.valeur } : {}),
        ...(exitType === 'rupture_conventionnelle' && pensionLiquidable ? { pension_liquidable: true } : {}),
        ...(exitType === 'fin_periode_essai' && initiativeEssai ? { probation_ended_by: initiativeEssai } : {}),
      };

      await createEmployeeExit(data);

      if (companyId) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.employees(companyId) });
        void queryClient.invalidateQueries({
          queryKey: queryKeys.employee(companyId, employeeId),
        });
        void queryClient.invalidateQueries({ queryKey: queryKeys.employeeExits(companyId) });
      }

      toast(
        messageDepartCree(
          exitType,
          lastWorkingDay,
          selectedEmployee ? `${selectedEmployee.first_name} ${selectedEmployee.last_name}` : undefined
        )
      );

      resetForm();
      onOpenChange(false);
      onSuccess?.();
    } catch (error: unknown) {
      log.error('Erreur lors de la création de la sortie:', error);
      toast({
        title: 'Erreur',
        description:
          (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          'Impossible de créer le processus de départ',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const showNoticeSection = preavisASaisir(exitType);

  const noticeDateWarning =
    noticePreview?.applicable &&
    noticePeriodDays > 0 &&
    lastWorkingDay &&
    exitRequestDate &&
    (() => {
      const minEndDate = new Date(exitRequestDate);
      minEndDate.setDate(minEndDate.getDate() + noticePeriodDays);
      return new Date(lastWorkingDay) < minEndDate;
    })()
      ? `Le dernier jour travaillé est antérieur à la fin théorique du préavis (${noticePeriodDays} jours). Vérifiez les dates ou indiquez une dispense.`
      : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nouveau départ de collaborateur</DialogTitle>
          <DialogDescription>
            Choisissez le type de départ : il pilote le workflow, les indemnités et les documents générés.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="employee">Employé *</Label>
            <Select value={employeeId} onValueChange={handleEmployeeChange} disabled={loadingEmployees}>
              <SelectTrigger id="employee">
                <SelectValue
                  placeholder={
                    loadingEmployees
                      ? 'Chargement...'
                      : employees.length === 0
                        ? 'Aucun collaborateur éligible'
                        : 'Sélectionner un employé'
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {employees.map((emp) => (
                  <SelectItem key={emp.id} value={emp.id}>
                    {emp.first_name} {emp.last_name} {emp.job_title ? `- ${emp.job_title}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {preselectionAbsente && (
              <p className="text-sm text-amber-700" data-testid="salarie-non-propose">
                Ce collaborateur n&apos;est pas proposé : un départ est déjà en cours pour lui, ou il
                a quitté l&apos;entreprise. Ouvrez le module Départs pour retrouver son dossier.
              </p>
            )}
            {!loadingEmployees && employees.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Seuls les collaborateurs actifs peuvent faire l&apos;objet d&apos;un départ. Un
                collaborateur déjà parti, ou dont un départ est déjà en cours, n&apos;apparaît pas ici.
              </p>
            )}
            {selectedEmployee?.contrat_absent && (
              <p className="text-sm text-muted-foreground" data-testid="contrat-absent-info">
                {CONTRAT_ABSENT_MESSAGE}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="exit_type">Type de départ *</Label>
            <Select value={exitType} onValueChange={(value) => handleExitTypeChange(value as ExitType)}>
              <SelectTrigger id="exit_type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="demission">Démission</SelectItem>
                <SelectItem value="rupture_conventionnelle">Rupture conventionnelle</SelectItem>
                <SelectItem value="licenciement">Licenciement</SelectItem>
                <SelectItem value="depart_retraite">Départ à la retraite</SelectItem>
                <SelectItem value="fin_periode_essai">Fin de période d&apos;essai</SelectItem>
                <SelectItem value="fin_cdd">Fin de CDD</SelectItem>
                <SelectItem value="transfert">Transfert intra-groupe</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="exit_request_date">
              {exitType === 'fin_periode_essai'
                ? 'Date de notification de la rupture *'
                : 'Date de demande/notification *'}
            </Label>
            <Input
              id="exit_request_date"
              type="date"
              value={exitRequestDate}
              onChange={(e) => {
                setExitRequestDate(e.target.value);
                noticeManuallyEdited.current = false;
              }}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="last_working_day">Dernier jour travaillé *</Label>
            <Input
              id="last_working_day"
              type="date"
              value={lastWorkingDay}
              onChange={(e) => setLastWorkingDay(e.target.value)}
              required
            />
          </div>

          {employeeId && showNoticeSection && (
            <div className="space-y-3">
              {loadingNoticePreview && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Calcul du préavis en cours…
                </div>
              )}

              {noticePreviewError && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Préavis non calculé</AlertTitle>
                  <AlertDescription>{noticePreviewError}</AlertDescription>
                </Alert>
              )}

              {noticePreview && !loadingNoticePreview && (
                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertTitle>
                    Préavis prévu : {noticePreview.label}
                    <span className="ml-2 font-normal text-muted-foreground">
                      ({libelleSourcePreavis(noticePreview.source)})
                    </span>
                  </AlertTitle>
                  <AlertDescription className="space-y-2">
                    <p>{noticePreview.detail}</p>
                    {noticePreview.has_collective_agreement && noticePreview.collective_agreement_name && (
                      <p className="text-sm">
                        Convention : <strong>{noticePreview.collective_agreement_name}</strong>
                        {noticePreview.collective_agreement_idcc
                          ? ` (IDCC ${noticePreview.collective_agreement_idcc})`
                          : ''}
                      </p>
                    )}
                    {!noticePreview.has_collective_agreement && (
                      <p className="text-sm text-muted-foreground">
                        Aucune convention collective assignée.
                      </p>
                    )}
                    {noticePreview.seniority_months != null && (
                      <p className="text-sm text-muted-foreground">
                        Ancienneté au {exitRequestDate} : {noticePreview.seniority_months} mois
                        {noticePreview.employee_category
                          ? ` · ${noticePreview.employee_category === 'cadre' ? 'Cadre' : 'Non-cadre'}`
                          : ''}
                      </p>
                    )}
                    {noticePreview.warnings.map((warning) => (
                      <p key={warning} className="text-sm text-amber-700 dark:text-amber-400">
                        {warning}
                      </p>
                    ))}
                    {noticeDateWarning && (
                      <p className="text-sm text-amber-700 dark:text-amber-400">{noticeDateWarning}</p>
                    )}
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}

          {showNoticeSection && (
            <>
              <div className="space-y-2">
                <Label htmlFor="notice_period_days">Durée du préavis (jours)</Label>
                <Input
                  id="notice_period_days"
                  type="number"
                  min="0"
                  value={noticePeriodDays}
                  onChange={(e) => handleNoticePeriodChange(parseInt(e.target.value, 10) || 0)}
                />
                <p className="text-sm text-muted-foreground">
                  Valeur proposée par la convention collective ou, pour un licenciement, un
                  départ ou une mise à la retraite, le Code du travail. La loi ne fixe pas de
                  préavis de démission : saisissez celui de la convention, du contrat ou des usages.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="notice_indemnity_type">Exécution du préavis</Label>
                <Select
                  value={noticeIndemnityType}
                  onValueChange={(value: TypePreavis) => setNoticeIndemnityType(value)}
                >
                  <SelectTrigger id="notice_indemnity_type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {OPTIONS_PREAVIS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </>
          )}

          {exitType === 'fin_periode_essai' && (
            <div className="space-y-2">
              <Label htmlFor="probation_ended_by">Rupture à l&apos;initiative de *</Label>
              <Select
                value={initiativeEssai}
                onValueChange={(value: InitiativeEssai) => setInitiativeEssai(value)}
              >
                <SelectTrigger id="probation_ended_by">
                  <SelectValue placeholder="Choisir" />
                </SelectTrigger>
                <SelectContent>
                  {OPTIONS_INITIATIVE_ESSAI.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">{AIDE_DELAI_PREVENANCE}</p>
            </div>
          )}

          {exitType === 'depart_retraite' && (
            <div className="space-y-2">
              <Label htmlFor="retirement_initiator">Initiative</Label>
              <Select
                value={initiativeRetraite}
                onValueChange={(value: InitiativeRetraite) => setInitiativeRetraite(value)}
              >
                <SelectTrigger id="retirement_initiator">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {OPTIONS_INITIATIVE_RETRAITE.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {indemniteConventionnelleSaisissable(exitType) && (
            <div className="space-y-2">
              <Label htmlFor="indemnite_conventionnelle">{LIBELLE_INDEMNITE_CONVENTIONNELLE}</Label>
              <Input
                id="indemnite_conventionnelle"
                inputMode="decimal"
                placeholder="Vide : minimum légal"
                value={indemniteConventionnelle}
                onChange={(e) => setIndemniteConventionnelle(e.target.value)}
              />
              <p className="text-sm text-muted-foreground">
                {aideIndemniteConventionnelle(exitType, initiativeRetraite)}
              </p>
            </div>
          )}

          {exitType === 'rupture_conventionnelle' && (
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="pension_liquidable"
                  checked={pensionLiquidable}
                  onCheckedChange={(checked) => setPensionLiquidable(checked === true)}
                />
                <Label htmlFor="pension_liquidable" className="cursor-pointer">
                  {LIBELLE_PENSION_LIQUIDABLE}
                </Label>
              </div>
              <p className="text-sm text-muted-foreground">{AIDE_PENSION_LIQUIDABLE}</p>
            </div>
          )}

          {exitType === 'licenciement' && (
            <div className="flex items-center space-x-2">
              <Checkbox
                id="is_gross_misconduct"
                checked={isGrossMisconduct}
                onCheckedChange={(checked) => {
                  setIsGrossMisconduct(checked as boolean);
                  noticeManuallyEdited.current = false;
                }}
              />
              <Label htmlFor="is_gross_misconduct" className="cursor-pointer">
                Faute grave ou lourde (pas d&apos;indemnité)
              </Label>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="exit_reason">Motif de départ</Label>
            <Textarea
              id="exit_reason"
              placeholder="Précision interne optionnelle : initiative salarié/employeur, contexte, référence courrier..."
              value={exitReason}
              onChange={(e) => setExitReason(e.target.value)}
              rows={3}
            />
            <p className="text-sm text-muted-foreground">
              Le type sélectionné ci-dessus est le motif juridique structurant. Ce champ sert seulement
              à ajouter une précision RH au dossier.
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Annuler
            </Button>
            <Button type="submit" disabled={loading || loadingEmployees || employees.length === 0}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Créer le départ
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
