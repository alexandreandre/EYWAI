import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { CheckCircle2, Loader2, X } from 'lucide-react';

import { updateEmployee } from '@/api/employees';
import * as collectiveAgreementsApi from '@/api/collectiveAgreements';
import { mutuelleTypesApi, type MutuelleType } from '@/api/mutuelleTypes';
import { getTeams } from '@/api/teams';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Form } from '@/components/ui/form';
import { toast } from '@/components/ui/use-toast';
import { EmployeeProfileEditForm } from '@/features/employee-detail/components/EmployeeProfileEditForm';
import {
  buildDefaultValues,
  buildUpdatePayload,
} from '@/features/employee-detail/components/employeeProfileFormUtils';
import {
  employeeProfileEditSchema,
  type EmployeeProfileEditFormValues,
} from '@/features/employee-detail/components/employeeProfileEditSchema';
import type { Employee } from '@/features/employee-detail/types';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';

export type EmployeeProfileEditVariant = 'onboarding' | 'edit';

export interface EmployeeProfileEditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employeeId: string;
  employee: Employee;
  variant: EmployeeProfileEditVariant;
  onSuccess: (employee: Employee) => void;
}

export function EmployeeProfileEditDialog({
  open,
  onOpenChange,
  employeeId,
  employee,
  variant,
  onSuccess,
}: EmployeeProfileEditDialogProps) {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();
  const [companyAgreements, setCompanyAgreements] = useState<
    collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails[]
  >([]);
  const [classificationsCc, setClassificationsCc] = useState<
    collectiveAgreementsApi.ClassificationConventionnelle[]
  >([]);
  const [activeTeams, setActiveTeams] = useState<Awaited<ReturnType<typeof getTeams>>['teams']>([]);
  const [availableMutuelles, setAvailableMutuelles] = useState<MutuelleType[]>([]);
  const [loadingMutuelles, setLoadingMutuelles] = useState(false);

  const defaultValues = useMemo(() => buildDefaultValues(employee), [employee]);
  const wasOnboarding = employee.employment_status === 'en_onboarding';

  const form = useForm<EmployeeProfileEditFormValues>({
    resolver: zodResolver(employeeProfileEditSchema),
    defaultValues,
  });

  const selectedCcId = form.watch('collective_agreement_id');

  useEffect(() => {
    if (open) {
      form.reset(buildDefaultValues(employee));
    }
  }, [open, employee, form]);

  useEffect(() => {
    if (!open) return;
    collectiveAgreementsApi.getMyCompanyAgreements()
      .then((res) => setCompanyAgreements(res.data ?? []))
      .catch(() => setCompanyAgreements([]));
    getTeams(false)
      .then((res) => setActiveTeams(res.teams ?? []))
      .catch(() => setActiveTeams([]));
    setLoadingMutuelles(true);
    mutuelleTypesApi.getMutuelleTypes()
      .then((list) => setAvailableMutuelles(list.filter((m) => m.is_active)))
      .catch(() => setAvailableMutuelles([]))
      .finally(() => setLoadingMutuelles(false));
  }, [open]);

  useEffect(() => {
    if (!open || !selectedCcId) {
      setClassificationsCc([]);
      return;
    }
    collectiveAgreementsApi.getClassifications(selectedCcId)
      .then((res) => setClassificationsCc(res.data ?? []))
      .catch(() => setClassificationsCc([]));
  }, [open, selectedCcId]);

  const saveMutation = useMutation({
    mutationFn: (values: EmployeeProfileEditFormValues) =>
      updateEmployee(employeeId, buildUpdatePayload(values, employee)),
    onSuccess: (updated) => {
      onSuccess(updated);
      if (companyId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.onboardingHubDashboard(companyId) });
        queryClient.invalidateQueries({ queryKey: queryKeys.employees(companyId) });
      }
      onOpenChange(false);
      const nowComplete =
        updated.profile_complete !== false && !(updated.missing_payroll_fields?.length);
      if (variant === 'onboarding' && nowComplete) {
        toast({
          title: 'Fiche complétée',
          description: wasOnboarding
            ? 'Le collaborateur est maintenant actif et prêt pour la paie.'
            : 'Les informations paie sont à jour.',
        });
      } else if (variant === 'edit') {
        toast({ title: 'Fiche mise à jour', description: 'Les informations ont été enregistrées.' });
      } else {
        toast({
          title: 'Informations enregistrées',
          description: 'Il reste des éléments à compléter sur la fiche.',
        });
      }
    },
    onError: (error: unknown) => {
      const detail =
        error &&
        typeof error === 'object' &&
        'response' in error &&
        (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      toast({
        title: 'Enregistrement impossible',
        description: typeof detail === 'string' ? detail : 'Vérifiez les champs saisis.',
        variant: 'destructive',
      });
    },
  });

  const fullName = `${employee.first_name} ${employee.last_name}`.trim();
  const title =
    variant === 'onboarding'
      ? `Finaliser l'onboarding — ${fullName}`
      : `Modifier la fiche — ${fullName}`;
  const description =
    variant === 'onboarding'
      ? 'Complétez la fiche en une seule fois pour finaliser l\'intégration du collaborateur.'
      : 'Modifiez les informations administratives, contractuelles et paie du collaborateur.';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            className="space-y-6"
            onSubmit={form.handleSubmit((values) => saveMutation.mutate(values))}
          >
            <EmployeeProfileEditForm
              control={form.control}
              companyAgreements={companyAgreements}
              classificationsCc={classificationsCc}
              activeTeams={activeTeams}
              availableMutuelles={availableMutuelles}
              loadingMutuelles={loadingMutuelles}
            />

            <DialogFooter className="gap-2 sm:gap-0">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={saveMutation.isPending}
              >
                <X className="mr-1.5 h-4 w-4" aria-hidden />
                Fermer
              </Button>
              <Button type="submit" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                    Enregistrement…
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="mr-2 h-4 w-4" aria-hidden />
                    {variant === 'onboarding' ? 'Enregistrer et finaliser' : 'Enregistrer'}
                  </>
                )}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
