import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import {
  Building2,
  Users,
  UserCircle,
  LifeBuoy,
  AlertTriangle,
  Radar,
  Plus,
  Shield,
  RefreshCw,
} from "lucide-react";
import { getAdminGlobalStats } from "@/api/adminEYWAI";
import { fetchDsnAdminLateSummary } from "@/api/dsnImport";
import { getActionLabel } from "@/lib/auditLabels";
import { queryKeys } from "@/lib/queryKeys";
import { AdminPageHeader } from "@/features/admin/components/eywai/AdminPageHeader";
import { AdminStatCard } from "@/features/admin/components/eywai/AdminStatCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrateur",
  rh: "RH",
  collaborateur_rh: "Collaborateur RH",
  manager: "Manager",
  salarie: "Salarié",
  collaborateur: "Collaborateur",
  custom: "Profil personnalisé",
};

const URGENCY_VARIANT: Record<string, "destructive" | "default" | "secondary" | "outline"> = {
  critique: "destructive",
  elevee: "destructive",
  normale: "secondary",
  faible: "outline",
};

export default function AdminDashboard() {
  const navigate = useNavigate();
  const {
    data: stats,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: queryKeys.adminGlobalStats(),
    queryFn: getAdminGlobalStats,
    placeholderData: (previous) => previous,
  });

  const { data: dsnLate } = useQuery({
    queryKey: ['dsn-admin-late-summary'],
    queryFn: fetchDsnAdminLateSummary,
    staleTime: 60_000,
  });

  useEffect(() => {
    const status = (error as { response?: { status?: number } } | null)?.response?.status;
    if (status === 403) {
      navigate("/");
    }
  }, [error, navigate]);

  if (isLoading && !stats) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      </div>
    );
  }

  if ((isError && !stats) || !stats) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <p className="text-destructive">Impossible de charger le tableau de bord.</p>
          <Button className="mt-4" onClick={() => void refetch()}>
            Réessayer
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      <AdminPageHeader
        title="Tableau de bord"
        description="Vue d'ensemble de la plateforme : organisations, utilisateurs, support et veille réglementaire."
        actions={
          <Button onClick={() => navigate("/super-admin/companies")}>
            <Plus className="mr-2 h-4 w-4" />
            Nouvelle entreprise
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <AdminStatCard
          title="Entreprises du groupe"
          value={stats.companies.total}
          subtitle={`${stats.companies.active} actives`}
          icon={Building2}
          onClick={() => navigate("/super-admin/companies")}
        />
        <AdminStatCard
          title="Utilisateurs"
          value={stats.users.total}
          subtitle={`${Object.keys(stats.users.by_role).length} types de profils`}
          icon={Users}
          onClick={() => navigate("/super-admin/users")}
        />
        <AdminStatCard
          title="Employés"
          value={stats.employees.total}
          subtitle="Sur toute la plateforme"
          icon={UserCircle}
        />
        <AdminStatCard
          title="Support à traiter"
          value={stats.support_tickets?.open ?? 0}
          subtitle={`${stats.support_tickets?.urgent ?? 0} priorité haute`}
          icon={LifeBuoy}
          variant={(stats.support_tickets?.open ?? 0) > 0 ? "warning" : "default"}
          onClick={() => navigate("/super-admin/support")}
        />
        <AdminStatCard
          title="Alertes veille"
          value={stats.scraping_alerts?.unread ?? 0}
          subtitle="Sources à vérifier"
          icon={Radar}
          variant={(stats.scraping_alerts?.unread ?? 0) > 0 ? "warning" : "default"}
          onClick={() => navigate("/super-admin/scraping")}
        />
        <AdminStatCard
          title="DSN en retard"
          value={dsnLate?.late_count ?? 0}
          subtitle="Paie externe / reprise"
          icon={RefreshCw}
          variant={(dsnLate?.late_count ?? 0) > 0 ? "warning" : "default"}
          onClick={() => navigate("/super-admin/companies?dsn=late")}
        />
        <AdminStatCard
          title="Équipe EYWAI"
          value={(stats.platform_admins ?? stats.super_admins)?.total ?? 0}
          subtitle="Accès plateforme"
          icon={Shield}
          onClick={() => navigate("/super-admin/admins")}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Demandes support récentes</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => navigate("/super-admin/support")}>
              Tout voir
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {(stats.recent_support_tickets ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune demande en cours.</p>
            ) : (
              stats.recent_support_tickets!.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className="flex w-full items-start justify-between gap-2 rounded-lg border p-3 text-left transition-colors hover:bg-muted/50"
                  onClick={() => navigate("/super-admin/support")}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {t.company_name ?? "Entreprise"} — {t.module}
                    </p>
                    <p className="line-clamp-1 text-xs text-muted-foreground">{t.description}</p>
                  </div>
                  <Badge variant={URGENCY_VARIANT[t.urgency] ?? "secondary"}>
                    {t.urgency}
                  </Badge>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Activité récente</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => navigate("/super-admin/activity")}>
              Journal complet
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {(stats.recent_activity ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune action journalisée récemment.</p>
            ) : (
              stats.recent_activity!.map((entry) => (
                <div
                  key={entry.id}
                  className="flex items-start justify-between gap-2 border-b pb-2 last:border-0 last:pb-0"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{getActionLabel(entry.action)}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {entry.user_email ?? "Système"} — {entry.company_name ?? entry.company_id.slice(0, 8)}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatActivityDate(entry.created_at)}
                  </span>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Utilisateurs par profil</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {Object.entries(stats.users.by_role).map(([role, count]) => (
              <div key={role} className="flex justify-between text-sm">
                <span className="text-muted-foreground">{ROLE_LABELS[role] ?? role}</span>
                <span className="font-medium tabular-nums">{count}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Entreprises les plus fournies</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {stats.top_companies.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune entreprise.</p>
            ) : (
              stats.top_companies.map((c, i) => (
                <button
                  key={c.id}
                  type="button"
                  className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-muted/50"
                  onClick={() => navigate(`/super-admin/companies/${c.id}`)}
                >
                  <span>
                    <span className="text-muted-foreground">#{i + 1} </span>
                    {c.name}
                  </span>
                  <span className="font-medium tabular-nums">{c.employees_count} salariés</span>
                </button>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border-dashed">
        <CardHeader>
          <CardTitle className="text-base">Raccourcis</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => navigate("/super-admin/access")}>
            <Shield className="mr-2 h-4 w-4" />
            Créer un profil RH
          </Button>
          <Button variant="outline" onClick={() => navigate("/super-admin/groups")}>
            <Building2 className="mr-2 h-4 w-4" />
            Voir le groupe
          </Button>
          <Button variant="outline" onClick={() => navigate("/super-admin/collective-agreements")}>
            Conventions collectives
          </Button>
          <Button variant="outline" onClick={() => navigate("/super-admin/scraping")}>
            <Radar className="mr-2 h-4 w-4" />
            Veille réglementaire
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function formatActivityDate(iso: string): string {
  try {
    return format(new Date(iso), "dd MMM HH:mm", { locale: fr });
  } catch {
    return iso;
  }
}
