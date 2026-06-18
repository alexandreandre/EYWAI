import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getCompanySettings,
  patchCompanySettings,
  type CompanySettingsResponse,
} from '@/api/company';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';
import {
  FRENCH_PUBLIC_HOLIDAY_DEFINITIONS,
  FRENCH_PUBLIC_HOLIDAY_IDS,
  LABOR_DAY_HOLIDAY_ID,
  getDefaultObservedHolidayIds,
  normalizeObservedHolidayIds,
  type FrenchPublicHolidayId,
} from '@/lib/frenchPublicHolidays';
import { CalendarDays } from 'lucide-react';

function readObservedIds(settings: CompanySettingsResponse | undefined): FrenchPublicHolidayId[] {
  const raw = settings?.settings?.public_holidays;
  if (!raw || typeof raw !== 'object') {
    return getDefaultObservedHolidayIds();
  }
  const ids = (raw as { observed_holiday_ids?: unknown }).observed_holiday_ids;
  if (!Array.isArray(ids)) {
    return getDefaultObservedHolidayIds();
  }
  return normalizeObservedHolidayIds(
    ids.filter((id): id is FrenchPublicHolidayId => typeof id === 'string')
  );
}

export default function PublicHolidaysSettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.companySettings(activeCompanyId),
    queryFn: getCompanySettings,
    enabled: Boolean(activeCompanyId),
  });

  const [observedIds, setObservedIds] = useState<FrenchPublicHolidayId[]>(
    getDefaultObservedHolidayIds()
  );

  useEffect(() => {
    if (data) {
      setObservedIds(readObservedIds(data));
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: (payload: FrenchPublicHolidayId[]) =>
      patchCompanySettings({
        public_holidays: { observed_holiday_ids: payload },
      }),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.companySettings(activeCompanyId), saved);
      setObservedIds(readObservedIds(saved));
      toast({
        title: 'Enregistré',
        description: 'Jours fériés chômés mis à jour pour le planning.',
      });
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Impossible d’enregistrer les jours fériés.',
        variant: 'destructive',
      });
    },
  });

  const toggleHoliday = (id: FrenchPublicHolidayId, checked: boolean) => {
    if (id === LABOR_DAY_HOLIDAY_ID) return;
    setObservedIds((prev) => {
      const set = new Set(prev);
      if (checked) {
        set.add(id);
      } else {
        set.delete(id);
      }
      set.add(LABOR_DAY_HOLIDAY_ID);
      return FRENCH_PUBLIC_HOLIDAY_IDS.filter((holidayId) => set.has(holidayId));
    });
  };

  const handleSave = () => {
    mutation.mutate(normalizeObservedHolidayIds(observedIds));
  };

  const isDirty = useMemo(() => {
    if (!data) return false;
    const saved = readObservedIds(data);
    if (saved.length !== observedIds.length) return true;
    return saved.some((id, index) => id !== observedIds[index]);
  }, [data, observedIds]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-full max-w-md" />
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <CardContent className="py-6 text-sm text-destructive">
          Impossible de charger les jours fériés de l&apos;entreprise.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center text-base">
          <CalendarDays className="mr-2 h-5 w-5 text-muted-foreground" />
          Jours fériés légaux
        </CardTitle>
        <CardDescription>
          Cochez les jours chômés au planning. Les jours décochés sont traités comme des jours
          ouvrés par défaut ; vous pouvez toujours ajuster salarié par salarié dans le calendrier.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          {FRENCH_PUBLIC_HOLIDAY_IDS.map((id) => {
            const isLaborDay = id === LABOR_DAY_HOLIDAY_ID;
            const checked = observedIds.includes(id);
            return (
              <div key={id} className="flex items-start gap-3 rounded-md border p-3">
                <Checkbox
                  id={`holiday-${id}`}
                  checked={checked}
                  disabled={!canEdit || isLaborDay}
                  onCheckedChange={(value) => toggleHoliday(id, value === true)}
                />
                <div className="space-y-1">
                  <Label htmlFor={`holiday-${id}`} className="font-medium leading-none">
                    {FRENCH_PUBLIC_HOLIDAY_DEFINITIONS[id].label}
                  </Label>
                  {isLaborDay ? (
                    <p className="text-xs text-muted-foreground">
                      Chômé obligatoire (jour férié légal).
                    </p>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>

        {canEdit ? (
          <div className="flex justify-end">
            <Button
              type="button"
              onClick={handleSave}
              disabled={!isDirty || mutation.isPending}
            >
              {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
