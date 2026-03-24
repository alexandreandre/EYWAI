// frontend/src/components/EmployeeCSEBlock.tsx
// Bloc CSE à afficher dans la fiche salarié (RH uniquement)

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { CSEBadge } from "@/components/CSEBadge";
import {
  getElectedMembers,
  getDelegationQuota,
  getDelegationHours,
  getMeetings,
} from "@/api/cse";
import { Users, Calendar, Clock, ArrowRight, Loader2 } from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";

interface EmployeeCSEBlockProps {
  employeeId: string;
}

function formatDate(dateString: string): string {
  try {
    return new Date(dateString).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return dateString;
  }
}

export function EmployeeCSEBlock({ employeeId }: EmployeeCSEBlockProps) {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id;

  // Charger le mandat actif
  const { data: members = [], isLoading: loadingMandate } = useQuery({
    queryKey: ["cse", "elected-members"],
    queryFn: () => getElectedMembers(true),
    enabled: !!companyId,
  });

  const mandate = members.find((m) => m.employee_id === employeeId);

  // Charger le quota de délégation (toujours appeler les hooks, avant tout return)
  const { data: quota } = useQuery({
    queryKey: ["cse", "delegation-quota", employeeId],
    queryFn: () => getDelegationQuota(employeeId),
    enabled: !!mandate && !!employeeId,
  });

  // Charger les heures de délégation (mois en cours)
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];

  const { data: hours = [] } = useQuery({
    queryKey: ["cse", "delegation-hours", employeeId, monthStart, monthEnd],
    queryFn: () => getDelegationHours(employeeId, monthStart, monthEnd),
    enabled: !!mandate && !!employeeId,
  });

  // Charger la prochaine réunion
  const { data: meetings = [] } = useQuery({
    queryKey: ["cse", "meetings", "upcoming"],
    queryFn: () => getMeetings("a_venir"),
    enabled: !!mandate,
  });

  // Retours conditionnels APRÈS tous les hooks
  if (!loadingMandate && !mandate) {
    return null;
  }

  // Note: La vérification des participants se fera côté backend
  // Pour l'instant, on prend la première réunion à venir
  const nextMeeting = meetings.length > 0 ? meetings[0] : null;

  const consumedHours = hours.reduce((sum, h) => sum + h.duration_hours, 0);
  const quotaHours = quota?.quota_hours_per_month || 0;
  const remainingHours = quotaHours - consumedHours;

  if (loadingMandate) {
    return (
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!mandate) {
    return null;
  }

  const daysRemaining = mandate.end_date
    ? Math.ceil(
        (new Date(mandate.end_date).getTime() - new Date().getTime()) /
          (1000 * 60 * 60 * 24)
      )
    : null;

  return (
    <Card className="border-blue-200 bg-blue-50/50">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="h-5 w-5 text-blue-600" />
            <span>CSE & Dialogue Social</span>
          </div>
          <CSEBadge
            role={mandate.role}
            college={mandate.college}
            startDate={mandate.start_date}
            endDate={mandate.end_date}
            daysRemaining={daysRemaining}
            compact
          />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Mandat en cours */}
        <div>
          <p className="text-sm font-medium text-muted-foreground mb-1">Mandat en cours</p>
          <div className="flex items-center gap-2 text-sm">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <span>
              Du {formatDate(mandate.start_date)} au {formatDate(mandate.end_date)}
            </span>
            {daysRemaining !== null && (
              <Badge variant={daysRemaining <= 90 ? "destructive" : "secondary"}>
                {daysRemaining > 0
                  ? `${daysRemaining} jour${daysRemaining > 1 ? "s" : ""} restant${daysRemaining > 1 ? "s" : ""}`
                  : "Expiré"}
              </Badge>
            )}
          </div>
        </div>

        {/* Compteur délégation */}
        {quota && (
          <div>
            <p className="text-sm font-medium text-muted-foreground mb-1">
              Heures de délégation (mois en cours)
            </p>
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <span>
                  {consumedHours.toFixed(1)}h / {quotaHours}h consommées
                </span>
              </div>
              <Badge variant={remainingHours < 0 ? "destructive" : remainingHours <= quotaHours * 0.2 ? "secondary" : "default"}>
                {remainingHours.toFixed(1)}h restantes
              </Badge>
            </div>
          </div>
        )}

        {/* Prochaine réunion */}
        {nextMeeting && (
          <div>
            <p className="text-sm font-medium text-muted-foreground mb-1">
              Prochaine réunion CSE
            </p>
            <div className="flex items-center gap-2 text-sm">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <span>{formatDate(nextMeeting.meeting_date)}</span>
              <span className="text-muted-foreground">- {nextMeeting.title}</span>
            </div>
          </div>
        )}

        {/* Lien vers le module CSE */}
        <div className="pt-2 border-t">
          <Button variant="outline" size="sm" asChild className="w-full">
            <Link to="/cse">
              Voir le détail dans le module CSE
              <ArrowRight className="h-4 w-4 ml-2" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
