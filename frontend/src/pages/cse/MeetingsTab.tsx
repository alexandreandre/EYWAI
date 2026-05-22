// frontend/src/pages/cse/MeetingsTab.tsx

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useToast } from "@/components/ui/use-toast";
import {
  getMeetings,
  updateMeetingStatus,
  type MeetingListItem,
  type MeetingStatus,
  type MeetingType,
} from "@/api/cse";
import {
  MEETING_STATUS_LABELS,
  MEETING_STATUS_BADGE_CLASSES,
  MEETING_TYPE_LABELS,
  RECORDING_STATUS_LABELS,
} from "@/lib/cseLabels";
import { Plus, Calendar, Users, Eye, Pencil, Play, Loader2 } from "lucide-react";
import { MeetingModal } from "@/components/cse/MeetingModal";
import { cn } from "@/lib/utils";

const STATUS_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "Toutes" },
  { value: "a_venir", label: MEETING_STATUS_LABELS.a_venir },
  { value: "en_cours", label: MEETING_STATUS_LABELS.en_cours },
  { value: "terminee", label: MEETING_STATUS_LABELS.terminee },
];

const TYPE_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "ordinaire", label: MEETING_TYPE_LABELS.ordinaire },
  { value: "extraordinaire", label: MEETING_TYPE_LABELS.extraordinaire },
  { value: "cssct", label: MEETING_TYPE_LABELS.cssct },
  { value: "autre", label: MEETING_TYPE_LABELS.autre },
];

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
  return timeString.substring(0, 5);
}

function truncateLocation(location: string | null | undefined, max = 28): string {
  if (!location?.trim()) return "—";
  const t = location.trim();
  return t.length > max ? `${t.slice(0, max)}…` : t;
}

function MeetingRecordingCell({ meeting }: { meeting: MeetingListItem }) {
  if (meeting.has_minutes) {
    return (
      <Badge variant="default" className="text-xs">
        PV disponible
      </Badge>
    );
  }
  if (meeting.recording_status) {
    const label =
      RECORDING_STATUS_LABELS[meeting.recording_status] ?? meeting.recording_status;
    const variant =
      meeting.recording_status === "failed"
        ? "destructive"
        : meeting.recording_status === "completed"
          ? "secondary"
          : "outline";
    return (
      <Badge variant={variant} className="text-xs">
        {label}
      </Badge>
    );
  }
  return <span className="text-muted-foreground text-xs">—</span>;
}

export default function MeetingsTab() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [meetingModalOpen, setMeetingModalOpen] = useState(false);
  const [selectedMeeting, setSelectedMeeting] = useState<MeetingListItem | null>(null);
  const [statusConfirm, setStatusConfirm] = useState<{
    meetingId: string;
    status: MeetingStatus;
    title: string;
  } | null>(null);

  const { data: meetings = [], isLoading } = useQuery({
    queryKey: ["cse", "meetings", statusFilter, typeFilter],
    queryFn: () =>
      getMeetings(
        statusFilter !== "all" ? (statusFilter as MeetingStatus) : undefined,
        typeFilter !== "all" ? (typeFilter as MeetingType) : undefined,
      ),
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ meetingId, status }: { meetingId: string; status: MeetingStatus }) =>
      updateMeetingStatus(meetingId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "meetings"] });
      toast({
        title: "Statut mis à jour",
        description: "Le statut de la réunion a été modifié.",
      });
      setStatusConfirm(null);
    },
    onError: (error: unknown) => {
      const msg =
        error && typeof error === "object" && "message" in error
          ? String((error as { message?: string }).message)
          : "Erreur lors de la mise à jour";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    },
  });

  const filteredMeetings = meetings.filter((meeting) => {
    if (!searchTerm) return true;
    const search = searchTerm.toLowerCase();
    return (
      meeting.title.toLowerCase().includes(search) ||
      formatDate(meeting.meeting_date).toLowerCase().includes(search)
    );
  });

  const openCreate = () => {
    setSelectedMeeting(null);
    setMeetingModalOpen(true);
  };

  const openEdit = (meeting: MeetingListItem) => {
    setSelectedMeeting(meeting);
    setMeetingModalOpen(true);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:flex-1">
          <Input
            placeholder="Rechercher une réunion…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-sm"
          />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full sm:w-[160px]">
              <SelectValue placeholder="Statut" />
            </SelectTrigger>
            <SelectContent>
              {STATUS_FILTER_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-full sm:w-[160px]">
              <SelectValue placeholder="Type" />
            </SelectTrigger>
            <SelectContent>
              {TYPE_FILTER_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={openCreate} className="shrink-0">
          <Plus className="h-4 w-4 mr-2" />
          Nouvelle réunion
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Réunions CSE</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : filteredMeetings.length === 0 ? (
            <div className="text-center py-10 space-y-3">
              <p className="text-muted-foreground">Aucune réunion ne correspond à vos critères.</p>
              <Button onClick={openCreate}>
                <Plus className="h-4 w-4 mr-2" />
                Planifier la prochaine réunion
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Titre</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Lieu</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Enregistrement / PV</TableHead>
                  <TableHead>Participants</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredMeetings.map((meeting) => (
                  <TableRow key={meeting.id}>
                    <TableCell className="font-medium">{meeting.title}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-muted-foreground shrink-0" />
                        <span>{formatDate(meeting.meeting_date)}</span>
                        {meeting.meeting_time && (
                          <span className="text-muted-foreground">
                            {formatTime(meeting.meeting_time)}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell
                      className="max-w-[140px] text-muted-foreground text-sm"
                      title={meeting.location?.trim() || undefined}
                    >
                      {truncateLocation(meeting.location)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {MEETING_TYPE_LABELS[meeting.meeting_type] ?? meeting.meeting_type}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={cn(
                          MEETING_STATUS_BADGE_CLASSES[meeting.status],
                          "border",
                        )}
                      >
                        {MEETING_STATUS_LABELS[meeting.status] ?? meeting.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <MeetingRecordingCell meeting={meeting} />
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Users className="h-4 w-4 text-muted-foreground" />
                        <span>{meeting.participant_count}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Voir le détail"
                          onClick={() => navigate(`/cse/meetings/${meeting.id}`)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Modifier"
                          onClick={() => openEdit(meeting)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        {meeting.status === "a_venir" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            title="Démarrer la réunion"
                            onClick={() =>
                              setStatusConfirm({
                                meetingId: meeting.id,
                                status: "en_cours",
                                title: meeting.title,
                              })
                            }
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                        )}
                        {meeting.status === "en_cours" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              setStatusConfirm({
                                meetingId: meeting.id,
                                status: "terminee",
                                title: meeting.title,
                              })
                            }
                          >
                            Terminer
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {meetingModalOpen && (
        <MeetingModal
          open={meetingModalOpen}
          onOpenChange={(open) => {
            setMeetingModalOpen(open);
            if (!open) setSelectedMeeting(null);
          }}
          meeting={selectedMeeting ?? undefined}
        />
      )}

      <AlertDialog open={!!statusConfirm} onOpenChange={(o) => !o && setStatusConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmer le changement de statut</AlertDialogTitle>
            <AlertDialogDescription>
              {statusConfirm?.status === "en_cours"
                ? `Démarrer la réunion « ${statusConfirm?.title} » ?`
                : `Marquer « ${statusConfirm?.title} » comme terminée ?`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (statusConfirm) {
                  updateStatusMutation.mutate({
                    meetingId: statusConfirm.meetingId,
                    status: statusConfirm.status,
                  });
                }
              }}
            >
              Confirmer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
