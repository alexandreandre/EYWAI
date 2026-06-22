import { useCallback, useEffect, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getModulationSettings } from '@/api/modulation';
import { RhPageHeader } from '@/components/layout';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ContingentHsTab } from '@/features/work-time-tracking/components/ContingentHsTab';
import { HourAccountTab } from '@/features/work-time-tracking/components/HourAccountTab';
import { WorkTimeHubIntro } from '@/features/work-time-tracking/components/WorkTimeHubIntro';
import {
  parseWorkTimeTab,
  type WorkTimeTab,
} from '@/features/work-time-tracking/lib/workTimeTabRouting';
import { useCompany } from '@/contexts/CompanyContext';
import { queryKeys } from '@/lib/queryKeys';
import { Clock, Gauge, Settings2 } from 'lucide-react';

export default function SuiviTempsTravailPage() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const [searchParams, setSearchParams] = useSearchParams();

  const activeTab = parseWorkTimeTab(searchParams.get('tab'));
  const selectedEmployeeId = searchParams.get('employee');

  const { data: modulationSettings } = useQuery({
    queryKey: queryKeys.modulationSettings(companyId),
    queryFn: getModulationSettings,
    enabled: Boolean(companyId),
  });

  const hourAccountVisible = useMemo(() => {
    if (!modulationSettings) return true;
    return modulationSettings.hour_account_enabled || modulationSettings.enabled;
  }, [modulationSettings]);

  const effectiveTab: WorkTimeTab =
    !hourAccountVisible && activeTab === 'compte-heures' ? 'contingent' : activeTab;

  useEffect(() => {
    if (!hourAccountVisible && activeTab === 'compte-heures') {
      const next = new URLSearchParams(searchParams);
      next.delete('tab');
      setSearchParams(next, { replace: true });
    }
  }, [hourAccountVisible, activeTab, searchParams, setSearchParams]);

  const updateSearchParams = useCallback(
    (updates: { tab?: WorkTimeTab; employee?: string | null }) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (updates.tab !== undefined) {
          if (updates.tab === 'contingent') {
            next.delete('tab');
          } else {
            next.set('tab', updates.tab);
          }
        }
        if (updates.employee !== undefined) {
          if (updates.employee) {
            next.set('employee', updates.employee);
          } else {
            next.delete('employee');
          }
        }
        return next;
      });
    },
    [setSearchParams],
  );

  const handleTabChange = (value: string) => {
    const tab = parseWorkTimeTab(value);
    updateSearchParams({ tab });
  };

  const handleEmployeeSelect = (employeeId: string | null) => {
    updateSearchParams({ employee: employeeId });
  };

  return (
    <div className="space-y-6">
      <RhPageHeader
        title="Temps de travail & HS"
        description="Pilotage du plafond annuel et du compte d'heures par salarié."
        actions={
          <Button variant="outline" size="sm" asChild>
            <Link to="/company?tab=paie&section=temps-travail">
              <Settings2 className="mr-2 h-4 w-4" />
              Paramètres
            </Link>
          </Button>
        }
      />

      <WorkTimeHubIntro />

      <Tabs value={effectiveTab} onValueChange={handleTabChange}>
        <TabsList className="grid w-full grid-cols-1 gap-1 sm:grid-cols-2 sm:w-auto">
          <TabsTrigger value="contingent" className="flex items-center gap-2">
            <Gauge className="h-4 w-4" />
            Plafond annuel (contingent)
          </TabsTrigger>
          {hourAccountVisible && (
            <TabsTrigger value="compte-heures" className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Compte d&apos;heures
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="contingent" className="mt-6">
          <ContingentHsTab
            initialEmployeeId={selectedEmployeeId}
            onEmployeeSelect={handleEmployeeSelect}
            hourAccountEnabled={hourAccountVisible}
          />
        </TabsContent>

        {hourAccountVisible && (
          <TabsContent value="compte-heures" className="mt-6">
            <HourAccountTab
              initialEmployeeId={selectedEmployeeId}
              onEmployeeSelect={handleEmployeeSelect}
            />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
