// frontend/src/pages/cse/MeetingDetail.tsx
// Détail d'une réunion CSE (RH ou élu avec accès API)

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  getMeetingDetail,
  getMeetingMinutesPathIfAvailable,
  getBDESDocuments,
  updateMeeting,
  updateMeetingStatus,
  updateMeetingParticipantAttendance,
  type MeetingStatus,
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
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  MEETING_STATUS_LABELS,
  MEETING_TYPE_LABELS,
} from "@/lib/cseLabels";
import {
  ArrowLeft,
  Calendar,
  MapPin,
  Users,
  FileText,
  Download,
  Loader2,
  ChevronRight,
  ExternalLink,
  Play,
  Square,
} from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

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

function extractNotesField(notes: unknown, key: string): string | null {
  if (notes == null || typeof notes !== "object") return null;
  const v = (notes as Record<string, unknown>)[key];
  if (typeof v === "string" && v.trim()) return v.trim();
  return null;
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

function extractAgendaText(agenda: unknown): string | null {
  if (agenda == null) return null;
  if (typeof agenda === "string" && agenda.trim()) return agenda.trim();
  if (typeof agenda !== "object") return null;
  const o = agenda as Record<string, unknown>;
  const text = o.text ?? o.content ?? o.ordre_du_jour;
  if (typeof text === "string" && text.trim()) return text.trim();
  return null;
}

function mergeNotes(
  existing: unknown,
  patch: Record<string, string | null>
): Record<string, unknown> {
  const base =
    existing != null && typeof existing === "object" && !Array.isArray(existing)
      ? { ...(existing as Record<string, unknown>) }
      : {};
  for (const [key, value] of Object.entries(patch)) {
    if (value == null || value === "") {
      delete base[key];
    } else {
      base[key] = value;
    }
  }
  return base;
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

  const { data: pdfPath } = useQuery({
    queryKey: ["cse", "minutes-path", meetingId],
    queryFn: () => getMeetingMinutesPathIfAvailable(meetingId!),
    enabled: Boolean(meetingId),
  });

  const { data: bdesDocs = [] } = useQuery({
    queryKey: ["cse", "bdes-linked", meetingYear],
    queryFn: () => getBDESDocuments(meetingYear),
    enabled: Boolean(meetingId) && meetingYear != null,
  });

  const pvText = meeting ? extractPvTextFromNotes(meeting.notes) : null;
  const notionUrl = meeting ? extractNotesField(meeting.notes, "notion_url") : null;
  const agendaText = meeting ? extractAgendaText(meeting.agenda) : null;

  const [draft, setDraft] = useState("");
  const [notionDraft, setNotionDraft] = useState("");

  useEffect(() => {
    setDraft(pvText ?? "");
    setNotionDraft(notionUrl ?? "");
  }, [meetingId, pvText, notionUrl]);

  const notesMutation = useMutation({
    mutationFn: (patch: Record<string, string | null>) =>
      updateMeeting(meetingId!, {
        notes: mergeNotes(meeting?.notes, patch),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "meeting-detail", meetingId] });
      queryClient.invalidateQueries({ queryKey: ["cse", "meetings"] });
      toast({
        title: "Notes enregistrées",
        description: "Les informations de la réunion ont été mises à jour.",
      });
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === "object" && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "")
          : "";
      toast({
        variant: "destructive",
        title: "Échec de l'enregistrement",
        description: msg || "Impossible d'enregistrer les notes.",
      });
    },
  });

  const statusMutation = useMutation({
    mutationFn: (status: MeetingStatus) => updateMeetingStatus(meetingId!, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "meeting-detail", meetingId] });
      queryClient.invalidateQueries({ queryKey: ["cse", "meetings"] });
      toast({
        title: "Statut mis à jour",
        description: "Le statut de la réunion a été modifié.",
      });
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === "object" && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "")
          : "";
      toast({
        variant: "destructive",
        title: "Erreur",
        description: msg || "Impossible de modifier le statut.",
      });
    },
  });

  const attendanceMutation = useMutation({
    mutationFn: ({ employeeId, attended }: { employeeId: string; attended: boolean }) =>
      updateMeetingParticipantAttendance(meetingId!, employeeId, attended),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "meeting-detail", meetingId] });
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de mettre à jour la présence.",
      });
    },
  });

  const notesDirty = (draft.trim() || "") !== (pvText ?? "");
  const notionDirty = (notionDraft.trim() || "") !== (notionUrl ?? "");

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

  const displayNotionUrl = notionUrl ?? (notionDraft.trim() || null);

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
            {rhActions && meeting.status === "a_venir" && (
              <Button
                size="sm"
                onClick={() => statusMutation.mutate("en_cours")}
                disabled={statusMutation.isPending}
              >
                {statusMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Play className="h-4 w-4 mr-2" />
                )}
                Démarrer la réunion
              </Button>
            )}
            {rhActions && meeting.status === "en_cours" && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => statusMutation.mutate("terminee")}
                disabled={statusMutation.isPending}
              >
                {statusMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Square className="h-4 w-4 mr-2" />
                )}
                Terminer la réunion
              </Button>
            )}
          </div>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Procès-verbal
          </CardTitle>
          <CardDescription>
            Saisissez vos notes pendant ou après la réunion
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {rhActions ? (
            <div className="space-y-3">
              <Textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Saisissez vos notes de réunion, points abordés, décisions prises…"
                className="min-h-[240px] resize-y"
              />
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  onClick={() =>
                    notesMutation.mutate({ pv_text: draft.trim() || null })
                  }
                  disabled={notesMutation.isPending || !notesDirty}
                >
                  {notesMutation.isPending ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : null}
                  Enregistrer les notes
                </Button>
                <p className="text-xs text-muted-foreground">
                  Visible par la RH et les élus participants.
                </p>
              </div>
            </div>
          ) : pvText ? (
            <div className="rounded-md border bg-muted/30 p-4 text-sm whitespace-pre-wrap">
              {pvText}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Aucun contenu textuel de PV renseigné sur cette réunion.
            </p>
          )}
          {pdfPath ? (
            <Button variant="default" size="sm" asChild>
              <a href={pdfPath} target="_blank" rel="noopener noreferrer" download>
                <Download className="h-4 w-4 mr-2" />
                Télécharger le PV (PDF)
              </a>
            </Button>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Notion</CardTitle>
          <CardDescription>
            Lien vers une page Notion pour prendre des notes en parallèle
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {displayNotionUrl ? (
            <Button variant="outline" size="sm" asChild>
              <a href={displayNotionUrl} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4 mr-2" />
                Ouvrir dans Notion
              </a>
            </Button>
          ) : null}
          {rhActions ? (
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <div className="flex-1 space-y-1">
                <Input
                  type="url"
                  value={notionDraft}
                  onChange={(e) => setNotionDraft(e.target.value)}
                  placeholder="https://www.notion.so/…"
                />
              </div>
              <Button
                size="sm"
                variant="secondary"
                onClick={() =>
                  notesMutation.mutate({ notion_url: notionDraft.trim() || null })
                }
                disabled={notesMutation.isPending || !notionDirty}
              >
                {notesMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : null}
                Enregistrer le lien
              </Button>
            </div>
          ) : !displayNotionUrl ? (
            <p className="text-sm text-muted-foreground">Aucun lien Notion renseigné.</p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Informations</CardTitle>
          <CardDescription>Date, lieu, ordre du jour, participants</CardDescription>
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
          </dl>
          {agendaText ? (
            <div>
              <p className="text-muted-foreground mb-2 font-medium">Ordre du jour</p>
              <div className="rounded-md border bg-muted/30 p-3 whitespace-pre-wrap text-sm">
                {agendaText}
              </div>
            </div>
          ) : null}
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
                          {rhActions ? (
                            <label className="inline-flex items-center gap-2 cursor-pointer">
                              <Checkbox
                                checked={p.attended}
                                disabled={attendanceMutation.isPending}
                                onCheckedChange={(checked) =>
                                  attendanceMutation.mutate({
                                    employeeId: p.employee_id,
                                    attended: checked === true,
                                  })
                                }
                              />
                              <span className="text-xs text-muted-foreground">
                                {p.attended ? "Présent" : "Absent"}
                              </span>
                            </label>
                          ) : p.attended ? (
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
          <CardTitle className="text-lg">Documents liés</CardTitle>
          <CardDescription>
            Documents BDES de l'année {meetingYear} (même exercice que la date de réunion)
          </CardDescription>
        </CardHeader>
        <CardContent>
          {bdesDocs.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun document BDES pour cette année.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {bdesDocs.map((doc) => (
                <li
                  key={doc.id}
                  className="flex flex-wrap items-center justify-between gap-2 border-b pb-2 last:border-0"
                >
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
