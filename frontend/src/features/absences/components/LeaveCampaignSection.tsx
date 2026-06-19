import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { AlertTriangle, CalendarCheck, CheckCircle2 } from 'lucide-react';
import {
  getLeaveCampaignDashboard,
  validateFractionnementGrants,
} from '@/api/cpFractionnement';
import { validateCpSeniorityGrants } from '@/api/cpSeniority';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';

export function LeaveCampaignSection() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [grantYear, setGrantYear] = useState(new Date().getFullYear());

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const dashboardQuery = useQuery({
    queryKey: queryKeys.leaveCampaignDashboard(companyId, grantYear),
    queryFn: () => getLeaveCampaignDashboard(grantYear),
    enabled: Boolean(companyId),
  });

  const validateCp = useMutation({
    mutationFn: () => validateCpSeniorityGrants(grantYear),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cpSeniorityPreview(companyId, grantYear) });
      void dashboardQuery.refetch();
      toast({
        title: 'CP ancienneté validés',
        description: `${res.validated_count} salarié(s) pour ${grantYear}.`,
      });
    },
  });

  const validateFrac = useMutation({
    mutationFn: () => validateFractionnementGrants(grantYear),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.fractionnementPreview(companyId, grantYear),
      });
      void dashboardQuery.refetch();
      toast({
        title: 'Fractionnement validé',
        description: `${res.validated_count} salarié(s) pour ${grantYear}.`,
      });
    },
  });

  const d = dashboardQuery.data;

  if (dashboardQuery.isLoading) {
    return (
      <Card>
        <CardHeader><Skeleton className="h-6 w-48" /></CardHeader>
        <CardContent><Skeleton className="h-24 w-full" /></CardContent>
      </Card>
    );
  }

  if (!d) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarCheck className="h-5 w-5" />
          Campagne congés {grantYear}
        </CardTitle>
        <CardDescription>
          Validation annuelle : CP ancienneté (fin mai) et fractionnement (fin octobre).
          Paramètres avancés dans Entreprise → Paie.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1">
            <Label htmlFor="campaign-year">Année</Label>
            <Input
              id="campaign-year"
              type="number"
              className="w-28"
              value={grantYear}
              onChange={(e) => setGrantYear(Number(e.target.value) || grantYear)}
            />
          </div>
          <Badge variant="outline">
            Phase : {d.phase === 'cp_seniority' ? 'CP ancienneté' : d.phase === 'fractionnement' ? 'Fractionnement' : 'Suivi'}
          </Badge>
        </div>

        {d.alerts.map((a) => (
          <Alert key={a.code} variant={a.level === 'warning' ? 'destructive' : 'default'}>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{a.message}</AlertDescription>
          </Alert>
        ))}

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border p-4 space-y-2">
            <p className="font-medium text-sm">CP ancienneté</p>
            {d.cp_seniority.enabled ? (
              <>
                <p className="text-sm text-muted-foreground">
                  {d.cp_seniority.employee_count} salarié(s) · {d.cp_seniority.total_days} j. ·{' '}
                  {d.cp_seniority.validated_count} validé(s)
                  {d.cp_seniority.warnings_count > 0
                    ? ` · ${d.cp_seniority.warnings_count} alerte(s)`
                    : ''}
                </p>
                <p className="text-xs text-muted-foreground">Échéance {d.cp_seniority.deadline}</p>
                {canEdit ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={validateCp.isPending}
                    onClick={() => validateCp.mutate()}
                  >
                    <CheckCircle2 className="mr-1 h-4 w-4" />
                    Valider tout
                  </Button>
                ) : null}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Non activé.</p>
            )}
          </div>

          <div className="rounded-lg border p-4 space-y-2">
            <p className="font-medium text-sm">Fractionnement</p>
            {d.fractionnement.enabled ? (
              <>
                <p className="text-sm text-muted-foreground">
                  {d.fractionnement.employee_count} salarié(s) · {d.fractionnement.total_days} j. ·{' '}
                  {d.fractionnement.validated_count} validé(s) · méthode {d.fractionnement.calculation_method}
                </p>
                <p className="text-xs text-muted-foreground">Échéance {d.fractionnement.deadline}</p>
                {canEdit ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={validateFrac.isPending}
                    onClick={() => validateFrac.mutate()}
                  >
                    <CheckCircle2 className="mr-1 h-4 w-4" />
                    Valider tout
                  </Button>
                ) : null}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Non activé.</p>
            )}
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          <Link to="/rh/company" className="underline">
            Configurer barèmes et formules
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
