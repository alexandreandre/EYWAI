// frontend/src/pages/employee/CSE.tsx
// Page CSE/BDES pour les élus (espace salarié)

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import {
  getMyElectedStatus,
  getMeetings,
  getDelegationQuota,
  getDelegationHours,
  getBDESDocuments,
  downloadBDESDocument,
  type MeetingListItem,
  type DelegationQuota,
  type DelegationHour,
  type BDESDocument,
} from "@/api/cse";
import {
  Calendar,
  Clock,
  FileText,
  CheckCircle2,
  Loader2,
  Users,
  AlertTriangle,
} from "lucide-react";
import { DelegationHourModal } from "@/components/cse/DelegationHourModal";

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

function formatTime(timeString: string | null): string {
  if (!timeString) return "";
  try {
    return timeString.substring(0, 5);
  } catch {
    return timeString;
  }
}

export default function EmployeeCSE() {
  const { toast } = useToast();
  const [hourModalOpen, setHourModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("meetings");

  // Vérifier le statut élu
  const { data: electedStatus, isLoading: loadingStatus } = useQuery({
    queryKey: ["cse", "my-elected-status"],
    queryFn: () => getMyElectedStatus(),
  });

  // Charger les réunions où l'utilisateur est participant
  const { data: meetings = [], isLoading: loadingMeetings } = useQuery({
    queryKey: ["cse", "my-meetings"],
    queryFn: () => getMeetings(),
    enabled: electedStatus?.is_elected === true,
  });

  // Charger le quota de délégation
  const { data: quota, isLoading: loadingQuota } = useQuery({
    queryKey: ["cse", "my-delegation-quota"],
    queryFn: () => getDelegationQuota(),
    enabled: electedStatus?.is_elected === true,
  });

  // Charger les heures de délégation (mois en cours)
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];

  const { data: hours = [], isLoading: loadingHours } = useQuery({
    queryKey: ["cse", "my-delegation-hours", monthStart, monthEnd],
    queryFn: () => getDelegationHours(undefined, monthStart, monthEnd),
    enabled: electedStatus?.is_elected === true,
  });

  // Charger les documents BDES
  const { data: bdesDocuments = [], isLoading: loadingBDES } = useQuery({
    queryKey: ["cse", "bdes-documents"],
    queryFn: () => getBDESDocuments(),
    enabled: electedStatus?.is_elected === true,
  });

  if (loadingStatus) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  // Si l'utilisateur n'est pas élu, afficher un message
  if (!electedStatus?.is_elected) {
    return (
      <div className="container mx-auto py-6">
        <Card className="border-orange-200">
          <CardContent className="pt-6">
            <div className="text-center">
              <AlertTriangle className="h-12 w-12 text-orange-500 mx-auto mb-4" />
              <h2 className="text-xl font-semibold mb-2">Accès non autorisé</h2>
              <p className="text-muted-foreground">
                Vous n'êtes pas élu CSE actif. Cet espace est réservé aux élus CSE.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const consumedHours = hours.reduce((sum, h) => sum + h.duration_hours, 0);
  const quotaHours = quota?.quota_hours_per_month || 0;
  const remainingHours = quotaHours - consumedHours;
  const isNearLimit = remainingHours <= quotaHours * 0.2 && remainingHours > 0;
  const isOverLimit = remainingHours < 0;

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header avec statut élu */}
      <div>
        <h1 className="text-3xl font-bold">CSE & Dialogue Social</h1>
        <p className="text-muted-foreground mt-1">
          Espace réservé aux élus CSE
        </p>
        {electedStatus.current_mandate && (
          <div className="mt-4">
            <Badge className="bg-blue-100 text-blue-800">
              {electedStatus.current_mandate.role.charAt(0).toUpperCase() + electedStatus.current_mandate.role.slice(1)}
              {electedStatus.current_mandate.college && ` - ${electedStatus.current_mandate.college}`}
            </Badge>
          </div>
        )}
      </div>

      {/* Compteur délégation (affiché en haut) */}
      <Card className="border-blue-200 bg-blue-50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Compteur de délégation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Quota mensuel</p>
              <p className="text-2xl font-bold">{quotaHours}h</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Consommé</p>
              <p className="text-2xl font-bold">{consumedHours.toFixed(1)}h</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Restant</p>
              <p className={`text-2xl font-bold ${isOverLimit ? "text-red-600" : isNearLimit ? "text-orange-600" : ""}`}>
                {remainingHours.toFixed(1)}h
              </p>
            </div>
          </div>
          {(isNearLimit || isOverLimit) && (
            <div className="mt-4 p-3 bg-orange-100 border border-orange-200 rounded-md">
              <p className="text-sm text-orange-900">
                {isOverLimit
                  ? `⚠️ Vous avez dépassé votre quota mensuel de ${Math.abs(remainingHours).toFixed(1)}h`
                  : `⚠️ Vous approchez de votre quota mensuel (${remainingHours.toFixed(1)}h restantes)`}
              </p>
            </div>
          )}
          <Button
            className="mt-4"
            onClick={() => setHourModalOpen(true)}
          >
            Saisir une heure de délégation
          </Button>
        </CardContent>
      </Card>

      {/* Onglets */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="meetings">
            <Calendar className="h-4 w-4 mr-2" />
            Ordres du jour
          </TabsTrigger>
          <TabsTrigger value="tasks">
            <CheckCircle2 className="h-4 w-4 mr-2" />
            Mes tâches
          </TabsTrigger>
          <TabsTrigger value="bdes">
            <FileText className="h-4 w-4 mr-2" />
            BDES
          </TabsTrigger>
          <TabsTrigger value="minutes">
            <FileText className="h-4 w-4 mr-2" />
            Historique PV
          </TabsTrigger>
          <TabsTrigger value="delegation">
            <Clock className="h-4 w-4 mr-2" />
            Mes heures
          </TabsTrigger>
        </TabsList>

        {/* Onglet Ordres du jour */}
        <TabsContent value="meetings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Mes réunions CSE</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingMeetings ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : meetings.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  Aucune réunion à afficher
                </div>
              ) : (
                <div className="space-y-4">
                  {meetings.map((meeting) => (
                    <Card key={meeting.id} className="border-l-4 border-l-blue-500">
                      <CardContent className="pt-4">
                        <div className="flex items-start justify-between">
                          <div>
                            <h3 className="font-semibold text-lg">{meeting.title}</h3>
                            <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                              <div className="flex items-center gap-2">
                                <Calendar className="h-4 w-4" />
                                {formatDate(meeting.meeting_date)}
                                {meeting.meeting_time && ` à ${formatTime(meeting.meeting_time)}`}
                              </div>
                              <Badge variant="outline">{meeting.meeting_type}</Badge>
                              <Badge
                                variant={
                                  meeting.status === "terminee"
                                    ? "default"
                                    : meeting.status === "en_cours"
                                    ? "secondary"
                                    : "outline"
                                }
                              >
                                {meeting.status === "terminee"
                                  ? "Terminée"
                                  : meeting.status === "en_cours"
                                  ? "En cours"
                                  : "À venir"}
                              </Badge>
                            </div>
                          </div>
                          <Button
                            variant="outline"
                            onClick={() => window.open(`/cse/meetings/${meeting.id}`, "_blank")}
                          >
                            Voir le détail
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Onglet Mes tâches */}
        <TabsContent value="tasks" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Mes tâches</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 text-muted-foreground">
                Les tâches extraites des PV seront affichées ici une fois les réunions traitées.
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Onglet BDES */}
        <TabsContent value="bdes" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Documents BDES</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingBDES ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : bdesDocuments.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  Aucun document BDES disponible
                </div>
              ) : (
                <div className="space-y-4">
                  {bdesDocuments.map((doc) => (
                    <Card key={doc.id}>
                      <CardContent className="pt-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="font-semibold">{doc.title}</h3>
                            <p className="text-sm text-muted-foreground mt-1">
                              {doc.description || "Aucune description"}
                            </p>
                            <div className="flex items-center gap-2 mt-2">
                              <Badge variant="outline">{doc.document_type}</Badge>
                              {doc.year && <Badge variant="secondary">{doc.year}</Badge>}
                            </div>
                          </div>
                          <Button
                            variant="outline"
                            onClick={async () => {
                              try {
                                const url = await downloadBDESDocument(doc.id);
                                window.open(url, "_blank");
                              } catch (error) {
                                toast({
                                  title: "Erreur",
                                  description: "Impossible de télécharger le document",
                                  variant: "destructive",
                                });
                              }
                            }}
                          >
                            <FileText className="h-4 w-4 mr-2" />
                            Télécharger
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Onglet Historique PV */}
        <TabsContent value="minutes" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Historique des procès-verbaux</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 text-muted-foreground">
                Les PV des réunions terminées seront affichés ici une fois générés.
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Onglet Mes heures */}
        <TabsContent value="delegation" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Mes heures de délégation</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingHours ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : hours.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  Aucune heure de délégation saisie ce mois
                </div>
              ) : (
                <div className="space-y-2">
                  {hours.map((hour) => (
                    <div
                      key={hour.id}
                      className="flex items-center justify-between p-3 border rounded-md"
                    >
                      <div>
                        <p className="font-medium">{formatDate(hour.date)}</p>
                        <p className="text-sm text-muted-foreground">{hour.reason}</p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold">{hour.duration_hours}h</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Modal saisie heure */}
      {hourModalOpen && (
        <DelegationHourModal
          open={hourModalOpen}
          onOpenChange={setHourModalOpen}
        />
      )}
    </div>
  );
}
