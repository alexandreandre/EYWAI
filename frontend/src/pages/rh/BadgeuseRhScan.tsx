import { RhPageHeader } from '@/components/layout';
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { isAxiosError } from "axios";
import { ArrowLeft, AlertTriangle, RefreshCw, UserX, Users } from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";
import { getBadgeuseDashboardToday } from "@/api/badgeuse";
import { QrScannerPanel } from "@/components/badgeuse/rh/QrScannerPanel";
import { BadgeuseFallbackPanel } from "@/components/badgeuse/rh/BadgeuseFallbackPanel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatTimeFr, eventTypeLabel } from "@/lib/badgeuseFormat";

function apiErrorDetail(error: unknown, fallback: string): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (error.response?.status === 503) {
      return "Service temporairement indisponible. Réessayez dans quelques secondes.";
    }
  }
  return fallback;
}

export default function BadgeuseRhScanPage() {
  const { activeCompany } = useCompany();
  const queryClient = useQueryClient();
  const companyId = activeCompany?.company_id;

  const {
    data: dashboard,
    isError: dashboardError,
    error: dashboardQueryError,
    refetch: refetchDashboard,
    isLoading: dashboardLoading,
  } = useQuery({
    queryKey: ["badgeuse", "dashboard-today", companyId],
    queryFn: () => getBadgeuseDashboardToday(companyId as string),
    enabled: !!companyId,
    refetchInterval: 30_000,
  });

  const dashboardErrorMessage = apiErrorDetail(
    dashboardQueryError,
    "Impossible de charger le tableau de bord du jour."
  );

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["badgeuse", "dashboard-today", companyId] });
    queryClient.invalidateQueries({ queryKey: ["badgeuse", "punch-candidates", companyId] });
    queryClient.invalidateQueries({ queryKey: ["badgeuse", "summary"] });
  };

  if (!companyId) {
    return <p className="text-sm text-muted-foreground">Aucune entreprise active.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/badgeuse-rh">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Pilotage
            </Link>
          </Button>
          <RhPageHeader
            title="Scan badgeuse"
            description="QR devant la caméra, ou secours sans téléphone ci-dessous"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-4 flex-1">
        <Card className="overflow-hidden">
          <div className="p-4 pb-0">
            <QrScannerPanel companyId={companyId} onScanSuccess={invalidate} />
          </div>
          <div className="border-t bg-muted/15 p-4">
            <BadgeuseFallbackPanel companyId={companyId} onSuccess={invalidate} />
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="p-4 space-y-3">
            <p className="text-xs font-medium uppercase text-muted-foreground tracking-wide">
              Aujourd&apos;hui
            </p>
            {dashboardError ? (
              <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-center">
                <p className="text-sm text-destructive">{dashboardErrorMessage}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-3 gap-2"
                  onClick={() => void refetchDashboard()}
                >
                  <RefreshCw className="h-4 w-4" />
                  Réessayer
                </Button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3">
                <div className="flex items-center gap-3 rounded-lg border p-3">
                  <Users className="h-5 w-5 text-emerald-600" />
                  <div>
                    <p className="text-2xl font-bold tabular-nums">
                      {dashboardLoading ? "…" : (dashboard?.present_count ?? "—")}
                    </p>
                    <p className="text-xs text-muted-foreground">En présence</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-lg border p-3">
                  <UserX className="h-5 w-5 text-slate-500" />
                  <div>
                    <p className="text-2xl font-bold tabular-nums">
                      {dashboardLoading ? "…" : (dashboard?.not_badged_count ?? "—")}
                    </p>
                    <p className="text-xs text-muted-foreground">Pas encore badgés</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-lg border p-3">
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                  <div>
                    <p className="text-2xl font-bold tabular-nums">
                      {dashboardLoading ? "…" : (dashboard?.anomaly_count ?? "—")}
                    </p>
                    <p className="text-xs text-muted-foreground">Anomalies</p>
                  </div>
                </div>
              </div>
            )}
          </Card>

          <Card className="p-4">
            <p className="text-sm font-semibold mb-3">Derniers scans</p>
            {dashboardError ? (
              <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-center">
                <p className="text-sm text-destructive">{dashboardErrorMessage}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2 gap-2"
                  onClick={() => void refetchDashboard()}
                >
                  <RefreshCw className="h-4 w-4" />
                  Réessayer
                </Button>
              </div>
            ) : dashboardLoading ? (
              <p className="text-sm text-muted-foreground">Chargement…</p>
            ) : dashboard?.last_scans?.length ? (
              <ul className="space-y-2 text-sm">
                {dashboard.last_scans.map((s, i) => (
                  <li key={`${s.timestamp}-${i}`} className="flex justify-between gap-2">
                    <span className="truncate font-medium">{s.employee_name}</span>
                    <span className="text-muted-foreground shrink-0">
                      {eventTypeLabel(s.event_type)} {formatTimeFr(s.timestamp)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Aucun scan pour le moment.</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
