// frontend/src/pages/cse/MeetingsTab.tsx
// Onglet Réunions CSE

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
import { useToast } from "@/components/ui/use-toast";
import {
  getMeetings,
  updateMeetingStatus,
  type MeetingListItem,
  type MeetingStatus,
} from "@/api/cse";
import { Plus, Calendar, Users, FileText, Play, Loader2 } from "lucide-react";
import { MeetingModal } from "@/components/cse/MeetingModal";
import { useNavigate } from "react-router-dom";

const STATUS_OPTIONS: { value: string; label: string; color: string }[] = [
  { value: "all", label: "Toutes", color: "" },
  { value: "a_venir", label: "À venir", color: "bg-blue-100 text-blue-800" },
  { value: "en_cours", label: "En cours", color: "bg-yellow-100 text-yellow-800" },
  { value: "terminee", label: "Terminée", color: "bg-green-100 text-green-800" },
];

const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "ordinaire", label: "Ordinaire" },
  { value: "extraordinaire", label: "Extraordinaire" },
  { value: "cssct", label: "CSSCT" },
  { value: "autre", label: "Autre" },
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
  try {
    return timeString.substring(0, 5); // HH:MM
  } catch {
    return timeString;
  }
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

  const { data: meetings = [], isLoading } = useQuery({
    queryKey: ["cse", "meetings", statusFilter, typeFilter],
    queryFn: () => getMeetings(
      statusFilter !== "all" ? (statusFilter as MeetingStatus) : undefined,
      typeFilter !== "all" ? (typeFilter as any) : undefined
    ),
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ meetingId, status }: { meetingId: string; status: MeetingStatus }) =>
      updateMeetingStatus(meetingId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "meetings"] });
      toast({
        title: "Statut mis à jour",
        description: "Le statut de la réunion a été modifié avec succès.",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Erreur",
        description: error.message || "Erreur lors de la mise à jour du statut",
        variant: "destructive",
      });
    },
  });

  const filteredMeetings = meetings.filter((meeting) => {
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      return (
        meeting.title.toLowerCase().includes(search) ||
        formatDate(meeting.meeting_date).toLowerCase().includes(search)
      );
    }
    return true;
  });

  const getStatusBadge = (status: MeetingStatus) => {
    const option = STATUS_OPTIONS.find((opt) => opt.value === status);
    return (
      <Badge className={option?.color || ""}>
        {option?.label || status}
      </Badge>
    );
  };

  return (
    <div className="space-y-4">
      {/* Header avec filtres */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 flex-1">
          <Input
            placeholder="Rechercher une réunion..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-sm"
          />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Statut" />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Type" />
            </SelectTrigger>
            <SelectContent>
              {TYPE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={() => setMeetingModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nouvelle réunion
        </Button>
      </div>

      {/* Liste des réunions */}
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
            <div className="text-center py-8 text-muted-foreground">
              Aucune réunion trouvée
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Titre</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Participants</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredMeetings.map((meeting) => (
                  <TableRow key={meeting.id}>
                    <TableCell className="font-medium">{meeting.title}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        <span>{formatDate(meeting.meeting_date)}</span>
                        {meeting.meeting_time && (
                          <span className="text-muted-foreground">
                            {formatTime(meeting.meeting_time)}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{meeting.meeting_type}</Badge>
                    </TableCell>
                    <TableCell>{getStatusBadge(meeting.status)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Users className="h-4 w-4 text-muted-foreground" />
                        <span>{meeting.participant_count}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/cse/meetings/${meeting.id}`)}
                        >
                          <FileText className="h-4 w-4" />
                        </Button>
                        {meeting.status === "a_venir" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              updateStatusMutation.mutate({
                                meetingId: meeting.id,
                                status: "en_cours",
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
                              updateStatusMutation.mutate({
                                meetingId: meeting.id,
                                status: "terminee",
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

      {/* Modal création/édition réunion */}
      {meetingModalOpen && (
        <MeetingModal
          open={meetingModalOpen}
          onOpenChange={setMeetingModalOpen}
          meeting={selectedMeeting || undefined}
        />
      )}
    </div>
  );
}
