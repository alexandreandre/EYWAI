import { HeartHandshake } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { isMutuelleMissing } from '@/features/employee-detail/components/employeeProfileFormUtils';
import type { Employee } from '@/features/employee-detail/types';
import {
  formatMutuelleAmountsLine,
  formatMutuelleOptionTitle,
  resolveOrganismeLabel,
} from '@/lib/mutuelleUtils';
import type { MutuelleType } from '@/api/mutuelleTypes';
import { useQuery } from '@tanstack/react-query';
import { mutuelleTypesApi } from '@/api/mutuelleTypes';
import { getPscSettings } from '@/api/pscSettings';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';

export interface RhOnboardingMutuelleBannerProps {
  employee: Employee;
  onOpenEdit: () => void;
}

function findAssignedMutuelle(
  employee: Employee,
  catalog: MutuelleType[],
): MutuelleType | null {
  const ids = employee.specificites_paie?.mutuelle?.mutuelle_type_ids;
  if (!Array.isArray(ids) || ids.length === 0) return null;
  return catalog.find((m) => m.id === ids[0]) ?? null;
}

export function RhOnboardingMutuelleBanner({
  employee,
  onOpenEdit,
}: RhOnboardingMutuelleBannerProps) {
  const companyId = useActiveCompanyId();
  const missing = isMutuelleMissing(employee);

  const { data: catalog = [] } = useQuery({
    queryKey: ['mutuelle-types', companyId],
    queryFn: () => mutuelleTypesApi.getMutuelleTypes(),
    enabled: Boolean(companyId) && !missing,
  });

  const { data: psc } = useQuery({
    queryKey: ['psc-settings', companyId],
    queryFn: getPscSettings,
    enabled: Boolean(companyId),
  });

  const organismeLabel = psc?.mutuelle_organisme_label?.trim();
  const organismeHint = organismeLabel ? organismeLabel : "l'organisme";

  const assigned = findAssignedMutuelle(employee, catalog);

  if (!missing && assigned) {
    const title = formatMutuelleOptionTitle(
      assigned,
      psc?.mutuelle_organisme_label ?? resolveOrganismeLabel(assigned, null),
    );
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50/80 px-4 py-3 text-emerald-950 print:hidden">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2">
            <HeartHandshake className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" aria-hidden />
            <div>
              <p className="text-sm font-medium">Mutuelle affectée</p>
              <p className="mt-0.5 text-sm text-emerald-900/90">
                {title} — {formatMutuelleAmountsLine(assigned)}
              </p>
            </div>
          </div>
          <Button type="button" size="sm" variant="outline" className="shrink-0" onClick={onOpenEdit}>
            Modifier
          </Button>
        </div>
      </div>
    );
  }

  if (!missing) return null;

  const fullName = `${employee.first_name} ${employee.last_name}`.trim();

  return (
    <div
      role="alert"
      className="rounded-lg border border-sky-200 bg-sky-50/80 px-4 py-3 text-sky-950 print:hidden"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-2">
          <HeartHandshake className="mt-0.5 h-5 w-5 shrink-0 text-sky-600" aria-hidden />
          <div>
            <p className="font-medium leading-snug">Mutuelle à renseigner</p>
            <p className="mt-1 text-sm text-sky-900/90">
              Sélectionnez la formule mutuelle de {fullName || 'ce collaborateur'} dans sa fiche
              (section Paie sociale), après son choix chez {organismeHint} ou son bulletin
              d&apos;adhésion.
            </p>
          </div>
        </div>
        <Button
          type="button"
          size="sm"
          className="shrink-0 gap-1.5 bg-sky-600 hover:bg-sky-700"
          onClick={onOpenEdit}
        >
          <HeartHandshake className="h-4 w-4" aria-hidden />
          Choisir la formule
        </Button>
      </div>
    </div>
  );
}
