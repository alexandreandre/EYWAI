// frontend/src/pages/CSE.tsx
// Page RH : Module CSE & Dialogue Social

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, Users, Calendar, Clock, FileText, CalendarDays, Download } from "lucide-react";
import { getMandateAlerts, getElectionAlerts } from "@/api/cse";
import type { MandateAlert, ElectionAlert } from "@/api/cse";

// Import des composants de chaque section
import MeetingsTab from "./cse/MeetingsTab";
import ElectedMembersTab from "./cse/ElectedMembersTab";
import DelegationHoursTab from "./cse/DelegationHoursTab";
import BDESTab from "./cse/BDESTab";
import ElectionCalendarTab from "./cse/ElectionCalendarTab";
import ExportsTab from "./cse/ExportsTab";

export default function CSE() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState("meetings");

  // Charger les alertes
  const { data: mandateAlerts = [], isLoading: loadingMandateAlerts } = useQuery({
    queryKey: ["cse", "mandate-alerts"],
    queryFn: () => getMandateAlerts(3),
  });

  const { data: electionAlerts = [], isLoading: loadingElectionAlerts } = useQuery({
    queryKey: ["cse", "election-alerts"],
    queryFn: () => getElectionAlerts(),
  });

  const totalAlerts = mandateAlerts.length + electionAlerts.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">CSE & Dialogue Social</h1>
          <p className="text-muted-foreground mt-1">
            Gestion des réunions CSE, élus, heures de délégation, BDES et calendrier électoral
          </p>
        </div>
        {totalAlerts > 0 && (
          <Card className="border-orange-200 bg-orange-50">
            <CardContent className="pt-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-orange-900">
                  {totalAlerts} alerte{totalAlerts > 1 ? "s" : ""}
                </span>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Alertes rapides */}
      {(mandateAlerts.length > 0 || electionAlerts.length > 0) && (
        <div className="grid gap-4 md:grid-cols-2">
          {mandateAlerts.length > 0 && (
            <Card className="border-orange-200">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  Alertes mandats
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {mandateAlerts.slice(0, 3).map((alert) => (
                    <div key={alert.elected_member_id} className="text-sm">
                      <span className="font-medium">
                        {alert.first_name} {alert.last_name}
                      </span>
                      {" - "}
                      <span className="text-muted-foreground">
                        Mandat expire dans {alert.days_remaining} jour{alert.days_remaining > 1 ? "s" : ""}
                      </span>
                    </div>
                  ))}
                  {mandateAlerts.length > 3 && (
                    <div className="text-sm text-muted-foreground">
                      + {mandateAlerts.length - 3} autre{alert.days_remaining > 1 ? "s" : ""}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {electionAlerts.length > 0 && (
            <Card className="border-red-200">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <CalendarDays className="h-5 w-5" />
                  Alertes électorales
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {electionAlerts.slice(0, 3).map((alert) => (
                    <div key={alert.cycle_id} className="text-sm">
                      <span className="font-medium">{alert.cycle_name}</span>
                      {" - "}
                      <span className="text-muted-foreground">{alert.message}</span>
                    </div>
                  ))}
                  {electionAlerts.length > 3 && (
                    <div className="text-sm text-muted-foreground">
                      + {electionAlerts.length - 3} autre{alert.days_remaining > 1 ? "s" : ""}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Onglets principaux */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="meetings" className="flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            Réunions
          </TabsTrigger>
          <TabsTrigger value="elected" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            Élus
          </TabsTrigger>
          <TabsTrigger value="delegation" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Délégation
          </TabsTrigger>
          <TabsTrigger value="bdes" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            BDES
          </TabsTrigger>
          <TabsTrigger value="elections" className="flex items-center gap-2">
            <CalendarDays className="h-4 w-4" />
            Élections
          </TabsTrigger>
          <TabsTrigger value="exports" className="flex items-center gap-2">
            <Download className="h-4 w-4" />
            Exports
          </TabsTrigger>
        </TabsList>

        <TabsContent value="meetings" className="space-y-4">
          <MeetingsTab />
        </TabsContent>

        <TabsContent value="elected" className="space-y-4">
          <ElectedMembersTab />
        </TabsContent>

        <TabsContent value="delegation" className="space-y-4">
          <DelegationHoursTab />
        </TabsContent>

        <TabsContent value="bdes" className="space-y-4">
          <BDESTab />
        </TabsContent>

        <TabsContent value="elections" className="space-y-4">
          <ElectionCalendarTab />
        </TabsContent>

        <TabsContent value="exports" className="space-y-4">
          <ExportsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
