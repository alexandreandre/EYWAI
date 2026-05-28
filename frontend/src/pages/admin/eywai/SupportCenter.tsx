import { useQuery } from "@tanstack/react-query";
import { LifeBuoy, Clock, CheckCircle2, AlertCircle } from "lucide-react";
import { getAdminGlobalStats } from "@/api/adminEYWAI";
import { AdminPageHeader } from "@/features/admin/components/eywai/AdminPageHeader";
import { AdminStatCard } from "@/features/admin/components/eywai/AdminStatCard";
import { Skeleton } from "@/components/ui/skeleton";
import TicketsHistoryPage from "@/pages/rh/support/TicketsHistoryPage";

export default function SupportCenter() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["admin", "dashboard-stats-support"],
    queryFn: getAdminGlobalStats,
    staleTime: 60_000,
  });

  const byStatus = stats?.support_tickets?.by_status ?? {};
  const resolvedWeek = (byStatus.resolu ?? 0) + (byStatus.cloture ?? 0);

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Centre support"
        description="Demandes remontées par les équipes RH et les utilisateurs — priorisez les urgences et suivez les délais de traitement."
      />

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          <AdminStatCard
            title="À traiter"
            value={stats?.support_tickets?.open ?? 0}
            subtitle={`${stats?.support_tickets?.urgent ?? 0} priorité haute`}
            icon={LifeBuoy}
            variant={(stats?.support_tickets?.open ?? 0) > 0 ? "warning" : "default"}
          />
          <AdminStatCard
            title="En cours"
            value={byStatus.en_cours ?? 0}
            subtitle="Pris en charge"
            icon={Clock}
          />
          <AdminStatCard
            title="Clôturés / résolus"
            value={resolvedWeek}
            subtitle="Sur la plateforme"
            icon={CheckCircle2}
            variant="success"
          />
        </div>
      )}

      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <AlertCircle className="h-3.5 w-3.5" />
        Les lignes en surbrillance orange ont plus de 48 h sans mise à jour (hors résolu/clôturé).
      </p>

      <TicketsHistoryPage />
    </div>
  );
}
