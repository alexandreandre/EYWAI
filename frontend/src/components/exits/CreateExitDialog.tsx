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
import { AlertCircle, Info, Loader2 } from 'lucide-react';

interface CreateExitDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

function noticeSourceLabel(source: NoticePeriodPreview['source']): string {
  switch (source) {
    case 'convention':
      return 'Convention collective';
    case 'legal':
      return 'Droit légal';
    case 'not_applicable':
      return 'Non applicable';
    default:
      return 'Non déterminé';
  }
}

export function CreateExitDialog({ open, onOpenChange, onSuccess }: CreateExitDialogProps) {
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
  const [noticeIndemnityType, setNoticeIndemnityType] = useState<'paid' | 'waived' | 'not_applicable'>('paid');
  const [exitReason, setExitReason] = useState<string>('');

  const resetForm = () => {
    setEmployeeId('');
    setExitType('demission');
    setExitRequestDate(new Date().toISOString().split('T')[0]);
    setLastWorkingDay('');
    setNoticePeriodDays(0);
    setIsGrossMisconduct(false);
    setNoticeIndemnityType('paid');
    setExitReason('');
    setNoticePreview(null);
    setNoticePreviewError(null);
    noticeManuallyEdited.current = false;
  };

  useEffect(() => {
    if (open) {
      fetchEmployees();
    } else {
      resetForm();
    }
  }, [open]);

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
          if (!preview.applicable || preview.notice_period_days === 0) {
            setNoticeIndemnityType('not_applicable');
          } else if (noticeIndemnityType === 'not_applicable') {
            setNoticeIndemnityType('paid');
          }
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
    setEmployeeId(value);
    noticeManuallyEdited.current = false;
  };

  const handleExitTypeChange = (value: ExitType) => {
    setExitType(value);
    noticeManuallyEdited.current = false;
    if (value !== 'licenciement') {
      setIsGrossMisconduct(false);
    }
    if (
      value === 'rupture_conventionnelle' ||
      value === 'depart_retraite'
    ) {
      setNoticePeriodDays(0);
      setNoticeIndemnityType('not_applicable');
    }
  };

  const handleNoticePeriodChange = (value: number) => {
    noticeManuallyEdited.current = true;
    setNoticePeriodDays(value);
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
      };

      await createEmployeeExit(data);

      if (companyId) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.employees(companyId) });
        void queryClient.invalidateQueries({
          queryKey: queryKeys.employee(companyId, employeeId),
        });
      }

      toast({
        title: 'Succès',
        description: 'Le processus de départ a été créé avec succès',
      });

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

  const showNoticeSection =
    exitType === 'demission' || exitType === 'licenciement' || exitType === 'fin_periode_essai';

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
            Créer un nouveau processus de départ (démission, rupture conventionnelle ou licenciement)
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
            {!loadingEmployees && employees.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Seuls les collaborateurs actifs disposant d&apos;un contrat de travail généré peuvent
                faire l&apos;objet d&apos;un départ.
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
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="exit_request_date">Date de demande/notification *</Label>
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
                      ({noticeSourceLabel(noticePreview.source)})
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
                        Aucune convention collective assignée — minima légaux appliqués.
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
                  Valeur pré-remplie selon la convention collective ou le droit légal. Ajustez si
                  nécessaire (dispense, clause contractuelle, etc.).
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="notice_indemnity_type">Indemnité de préavis</Label>
                <Select
                  value={noticeIndemnityType}
                  onValueChange={(value: 'paid' | 'waived' | 'not_applicable') =>
                    setNoticeIndemnityType(value)
                  }
                >
                  <SelectTrigger id="notice_indemnity_type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="paid">Payée (préavis effectué)</SelectItem>
                    <SelectItem value="waived">Dispensée (préavis non effectué, payé)</SelectItem>
                    <SelectItem value="not_applicable">Non applicable</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </>
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
              placeholder="Raison du départ (optionnel)"
              value={exitReason}
              onChange={(e) => setExitReason(e.target.value)}
              rows={3}
            />
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
