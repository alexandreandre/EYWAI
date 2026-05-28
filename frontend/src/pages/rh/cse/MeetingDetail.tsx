// frontend/src/pages/cse/MeetingDetail.tsx
// Détail d'une réunion CSE (RH ou élu avec accès API)

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  getMeetingDetail,
  getRecordingStatus,
  getMeetingMinutesPathIfAvailable,
  getBDESDocuments,
  processRecording,
} from "@/api/cse";
import { useAuth } from "@/contexts/AuthContext";
import {
  EmployeePageBackLink,
  EmployeePageHeader,
  EmployeePageShell,
} from "@/components/employee/EmployeePageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  MEETING_STATUS_LABELS,
  MEETING_TYPE_LABELS,
} from "@/lib/cseLabels";
import { ArrowLeft, Calendar, MapPin, Users, FileText, Download, Sparkles, Loader2, ChevronRight } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

const RECORDING_STATUS_LABELS: Record<string, string> = {
  not_started: "Non démarré",
  in_progress: "En cours",
  completed: "Terminé",
  failed: "Échec",
};

function formatDate(dateString: string): string {
  try {
    return new Date(dateString).toLocaleDateString("fr-FR", {
      weekday: "long",
      day: "2-digit",
      month: "long",
      year: "numeric",
    });
  } catch {
    return dateString;
  }
}

function formatTime(time: string | null | undefined): string {
  if (!time) return "—";
  try {
    return time.substring(0, 5);
  } catch {
    return String(time);
  }
}

function extractPvTextFromNotes(notes: unknown): string | null {
  if (notes == null) return null;
  if (typeof notes === "string" && notes.trim()) return notes.trim();
  if (typeof notes !== "object") return null;
  const o = notes as Record<string, unknown>;
  const keys = ["pv_text", "minutes_text", "contenu_pv", "summary", "resume", "texte_pv", "texte"];
  for (const k of keys) {
    const v = o[k];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return null;
}

function canUseRhCseActions(role: string | undefined): boolean {
  return role === "rh" || role === "admin" || role === "collaborateur_rh";
}

export default function MeetingDetail() {
  const { meetingId } = useParams<{ meetingId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const rhActions = canUseRhCseActions(user?.role);

  const {
    data: meeting,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["cse", "meeting-detail", meetingId],
    queryFn: () => getMeetingDetail(meetingId!),
    enabled: Boolean(meetingId),
  });

  const meetingYear = meeting?.meeting_date
    ? new Date(meeting.meeting_date).getFullYear()
    : undefined;

  const {
    data: recording,
    isError: recordingError,
    isLoading: recordingLoading,
  } = useQuery({
    queryKey: ["cse", "recording", meetingId],
    queryFn: () => getRecordingStatus(meetingId!),
    enabled: Boolean(meetingId),
    retry: false,
  });

  const { data: pdfPath, refetch: refetchMinutesPath } = useQuery({
    queryKey: ["cse", "minutes-path", meetingId],
    queryFn: () => getMeetingMinutesPathIfAvailable(meetingId!),
    enabled: Boolean(meetingId),
  });

  const { data: bdesDocs = [] } = useQuery({
    queryKey: ["cse", "bdes-linked", meetingYear],
    queryFn: () => getBDESDocuments(meetingYear),
    enabled: Boolean(meetingId) && meetingYear != null,
  });

  const processMutation = useMutation({
    mutationFn: () => processRecording(meetingId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "recording", meetingId] });
      queryClient.invalidateQueries({ queryKey: ["cse", "minutes-path", meetingId] });
      queryClient.invalidateQueries({ queryKey: ["cse", "meeting-detail", meetingId] });
      void refetchMinutesPath();
      toast({
        title: "Traitement lancé",
        description: "Le traitement d’enregistrement a été exécuté. Actualisez si le PV met du temps à apparaître.",
      });
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === "object" && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "")
          : "";
      toast({
        variant: "destructive",
        title: "Échec du traitement",
        description: msg || "Impossible de traiter l’enregistrement.",
      });
    },
  });

  const pvText = meeting ? extractPvTextFromNotes(meeting.notes) : null;
  const showGeneratePv =
    rhActions &&
    !pdfPath &&
    recording &&
    recording.status !== "not_started" &&
    !recording.has_minutes;

  if (!meetingId) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" onClick={() => navigate("/cse")}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Retour
        </Button>
        <p className="text-sm text-muted-foreground">Identifiant de réunion manquant.</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-10 w-full max-w-xl" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !meeting) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/cse">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Retour au module CSE
          </Link>
        </Button>
        <Card>
          <CardHeader>
            <CardTitle>Réunion introuvable</CardTitle>
            <CardDescription>
              {error instanceof Error ? error.message : "Impossible de charger cette réunion."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" onClick={() => navigate("/cse")}>
              Retour à la liste
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  function formatParticipantDate(iso: string | null | undefined): string {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleDateString("fr-FR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  }

  return (
    <EmployeePageShell className="pb-4">
      <nav className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link to="/cse" className="hover:text-foreground">
          CSE / BDES
        </Link>
        <ChevronRight className="h-4 w-4" />
        <Link to="/cse" className="hover:text-foreground">
          Réunions
        </Link>
        <ChevronRight className="h-4 w-4" />
        <span className="text-foreground font-medium truncate max-w-[200px]">
          {meeting.title}
        </span>
      </nav>
      <EmployeePageHeader
        back={<EmployeePageBackLink to="/cse" label="Retour aux réunions" />}
        title={meeting.title}
        afterDescription={
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="secondary">
              {MEETING_STATUS_LABELS[meeting.status]}
            </Badge>
            <span className="inline-flex items-center gap-1">
              <Calendar className="h-4 w-4" />
              {formatDate(meeting.meeting_date)} à {formatTime(meeting.meeting_time)}
            </span>
            <Badge variant="outline">
              {MEETING_TYPE_LABELS[meeting.meeting_type]}
            </Badge>
          </div>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Informations</CardTitle>
          <CardDescription>Date, lieu, participants</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Date</dt>
              <dd className="font-medium">{formatDate(meeting.meeting_date)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Heure</dt>
              <dd className="font-medium">{formatTime(meeting.meeting_time)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Lieu</dt>
              <dd className="font-medium flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                {meeting.location?.trim() ? meeting.location : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Type</dt>
              <dd className="font-medium">{MEETING_TYPE_LABELS[meeting.meeting_type]}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Statut</dt>
              <dd className="font-medium">{MEETING_STATUS_LABELS[meeting.status]}</dd>
            </div>
          </dl>
          <div>
            <p className="text-muted-foreground mb-2 flex items-center gap-2">
              <Users className="h-4 w-4" />
              Participants ({meeting.participants?.length ?? meeting.participant_count ?? 0})
            </p>
            {(meeting.participants ?? []).length > 0 ? (
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50 text-left">
                      <th className="p-2 font-medium">Nom</th>
                      <th className="p-2 font-medium">Confirmé</th>
                      <th className="p-2 font-medium">Présent</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(meeting.participants ?? []).map((p) => (
                      <tr key={p.employee_id} className="border-b last:border-0">
                        <td className="p-2">
                          {[p.first_name, p.last_name].filter(Boolean).join(" ") ||
                            p.employee_id}
                          {p.job_title ? (
                            <span className="text-muted-foreground block text-xs">
                              {p.job_title}
                            </span>
                          ) : null}
                        </td>
                        <td className="p-2 text-muted-foreground">
                          {formatParticipantDate(p.confirmed_at)}
                        </td>
                        <td className="p-2">
                          {p.attended ? (
                            <Badge variant="outline" className="text-green-700 border-green-200">
                              Oui
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">Non</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Aucun participant renseigné.</p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Enregistrement</CardTitle>
          <CardDescription>Statut de l’enregistrement et synthèse</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {recordingLoading ? (
            <p className="text-muted-foreground">Chargement du statut…</p>
          ) : recordingError ? (
            <p className="text-muted-foreground">Statut d’enregistrement non accessible.</p>
          ) : recording ? (
            <>
              <p>
                <span className="text-muted-foreground">Statut : </span>
                <span className="font-medium">
                  {RECORDING_STATUS_LABELS[recording.status] ?? recording.status}
                </span>
              </p>
              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                {recording.has_transcription && <Badge variant="outline">Transcription</Badge>}
                {recording.has_summary && <Badge variant="outline">Synthèse IA</Badge>}
                {recording.has_minutes && <Badge variant="outline">PV généré</Badge>}
              </div>
              {recording.error_message && (
                <p className="text-destructive text-sm">{recording.error_message}</p>
              )}
              <p className="text-muted-foreground text-xs">
                La lecture audio n’est pas exposée par l’API actuelle ; utilisez le traitement puis le
                PV pour conserver la trace écrite.
              </p>
            </>
          ) : (
            <p className="text-muted-foreground">Aucune donnée d’enregistrement.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Procès-verbal
          </CardTitle>
          <CardDescription>Synthèse textuelle et document PDF</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {pvText ? (
            <div className="rounded-md border bg-muted/30 p-4 text-sm whitespace-pre-wrap">{pvText}</div>
          ) : recording?.has_summary ? (
            <p className="text-sm text-muted-foreground">
              Une synthèse est disponible côté serveur ; le texte détaillé peut être joint au PDF une
              fois généré.
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">Aucun contenu textuel de PV renseigné sur cette réunion.</p>
          )}
          <div className="flex flex-wrap gap-2">
            {pdfPath ? (
              <Button variant="default" size="sm" asChild>
                <a href={pdfPath} target="_blank" rel="noopener noreferrer" download>
                  <Download className="h-4 w-4 mr-2" />
                  Télécharger le PV
                </a>
              </Button>
            ) : null}
            {showGeneratePv ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => processMutation.mutate()}
                disabled={processMutation.isPending}
              >
                {processMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4 mr-2" />
                )}
                Générer le PV à partir de l’enregistrement
              </Button>
            ) : null}
          </div>
          {!pdfPath && !showGeneratePv && rhActions && (
            <p className="text-xs text-muted-foreground">
              Pour générer un procès-verbal, terminez l’enregistrement de la réunion puis lancez la
              génération lorsque le traitement est disponible.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Documents liés</CardTitle>
          <CardDescription>
            Documents BDES de l’année {meetingYear} (même exercice que la date de réunion)
          </CardDescription>
        </CardHeader>
        <CardContent>
          {bdesDocs.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun document BDES pour cette année.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {bdesDocs.map((doc) => (
                <li key={doc.id} className="flex flex-wrap items-center justify-between gap-2 border-b pb-2 last:border-0">
                  <span className="font-medium">{doc.title}</span>
                  <span className="text-muted-foreground text-xs">{doc.document_type}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </EmployeePageShell>
  );
}
