// frontend/src/components/CSEDashboardBlock.tsx
// Bloc CSE pour le dashboard RH

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Link, useNavigate } from "react-router-dom";
import {
  getMandateAlerts,
  getElectionAlerts,
  getMeetings,
  getDelegationSummary,
} from "@/api/cse";
import {
  Handshake,
  Calendar,
  Users,
  Clock,
  AlertTriangle,
  ArrowRight,
  Loader2,
} from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";

export function CSEDashboardBlock() {
  const navigate = useNavigate();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id;

  // Vérifier si le module CSE est activé
  // Note: Pour l'instant, on affiche toujours le bloc
  // Dans une version future, vérifier l'activation via API

  // Charger les alertes
  const { data: mandateAlerts = [], isLoading: loadingMandateAlerts } = useQuery({
    queryKey: ["cse", "mandate-alerts"],
    queryFn: () => getMandateAlerts(3),
    enabled: !!companyId,
  });

  const { data: electionAlerts = [], isLoading: loadingElectionAlerts } = useQuery({
    queryKey: ["cse", "election-alerts"],
    queryFn: () => getElectionAlerts(),
    enabled: !!companyId,
  });

  // Charger la prochaine réunion
  const { data: meetings = [] } = useQuery({
    queryKey: ["cse", "meetings", "upcoming"],
    queryFn: () => getMeetings("a_venir"),
    enabled: !!companyId,
  });

  const nextMeeting = meetings.length > 0 ? meetings[0] : null;

  // Charger le récapitulatif des heures de délégation (mois en cours)
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];

  const { data: delegationSummary = [] } = useQuery({
    queryKey: ["cse", "delegation-summary", monthStart, monthEnd],
    queryFn: () => getDelegationSummary(monthStart, monthEnd),
    enabled: !!companyId,
  });

  const totalConsumedHours = delegationSummary.reduce(
    (sum, item) => sum + item.consumed_hours,
    0
  );

  const totalAlerts = mandateAlerts.length + electionAlerts.length;

  if (loadingMandateAlerts || loadingElectionAlerts) {
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

  // Si aucune donnée CSE, afficher une carte minimaliste (raccourci vers /cse)
  if (mandateAlerts.length === 0 && electionAlerts.length === 0 && !nextMeeting && delegationSummary.length === 0) {
    return (
      <Card className="border-blue-200 bg-blue-50/50 hover:shadow-md transition-shadow cursor-pointer h-full min-h-[88px]" onClick={() => navigate("/cse")}>
        <CardContent className="p-4 flex items-center gap-4">
          <div className="p-3 rounded-lg bg-blue-100 text-blue-600">
            <Handshake className="h-6 w-6" />
          </div>
          <div>
            <p className="font-semibold text-foreground">CSE & Dialogue social</p>
            <p className="text-xs text-muted-foreground">Réunions, élus, BDES</p>
          </div>
          <ArrowRight className="h-5 w-5 text-muted-foreground ml-auto" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-blue-200 bg-blue-50/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Handshake className="h-5 w-5 text-blue-600" />
          CSE & Dialogue Social
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Prochaine réunion — date en gras */}
        {nextMeeting && (
          <div>
            <p className="text-sm font-medium text-muted-foreground mb-1">
              Prochaine réunion
            </p>
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <span className="font-bold text-foreground">
                {new Date(nextMeeting.meeting_date).toLocaleDateString("fr-FR", {
                  weekday: "short",
                  day: "2-digit",
                  month: "short",
                  year: "numeric",
                })}
              </span>
              <span className="text-sm text-muted-foreground truncate">
                {nextMeeting.title}
              </span>
            </div>
          </div>
        )}

        {/* Compteur alertes */}
        {totalAlerts > 0 && (
          <div>
            <p className="text-sm font-medium text-muted-foreground mb-1">Alertes</p>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-orange-500" />
              <span className="font-semibold text-orange-600">
                {totalAlerts} alerte{totalAlerts > 1 ? "s" : ""}
              </span>
              {mandateAlerts.length > 0 && (
                <Badge variant="outline" className="text-xs">
                  {mandateAlerts.length} mandat{mandateAlerts.length > 1 ? "s" : ""}
                </Badge>
              )}
              {electionAlerts.length > 0 && (
                <Badge variant="outline" className="text-xs">
                  {electionAlerts.length} élection{electionAlerts.length > 1 ? "s" : ""}
                </Badge>
              )}
            </div>
          </div>
        )}

        {/* Heures de délégation consommées */}
        {delegationSummary.length > 0 && (
          <div>
            <p className="text-sm font-medium text-muted-foreground mb-1">
              Heures de délégation (mois en cours)
            </p>
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="font-semibold">
                {totalConsumedHours.toFixed(1)}h consommées
              </span>
            </div>
          </div>
        )}

        {/* Lien vers le module */}
        <Button variant="outline" size="sm" asChild className="w-full">
          <Link to="/cse">
            Accéder au module CSE
            <ArrowRight className="h-4 w-4 ml-2" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
