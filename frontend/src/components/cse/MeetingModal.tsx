// frontend/src/components/cse/MeetingModal.tsx

import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import {
  createMeeting,
  updateMeeting,
  getMeetingById,
  addMeetingParticipants,
  getElectedMembers,
  type MeetingCreate,
  type MeetingUpdate,
  type MeetingListItem,
} from "@/api/cse";
import { MEETING_TYPE_LABELS } from "@/lib/cseLabels";
import { Loader2 } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

interface MeetingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  meeting?: MeetingListItem;
}

export function MeetingModal({ open, onOpenChange, meeting }: MeetingModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [meetingDate, setMeetingDate] = useState("");
  const [meetingTime, setMeetingTime] = useState("");
  const [location, setLocation] = useState("");
  const [meetingType, setMeetingType] = useState<
    "ordinaire" | "extraordinaire" | "cssct" | "autre"
  >("ordinaire");
  const [participantIds, setParticipantIds] = useState<string[]>([]);

  const { data: electedMembers = [] } = useQuery({
    queryKey: ["cse", "elected-members", "meeting-modal"],
    queryFn: () => getElectedMembers(true),
    enabled: open,
  });

  const { data: meetingDetail, isLoading: loadingDetail } = useQuery({
    queryKey: ["cse", "meeting-detail", meeting?.id, "modal"],
    queryFn: () => getMeetingById(meeting!.id),
    enabled: open && !!meeting?.id,
  });

  useEffect(() => {
    if (!open) return;
    if (meeting && meetingDetail) {
      setTitle(meetingDetail.title);
      setMeetingDate(meetingDetail.meeting_date.split("T")[0]);
      setMeetingTime(meetingDetail.meeting_time?.substring(0, 5) || "");
      setLocation(meetingDetail.location || "");
      setMeetingType(meetingDetail.meeting_type);
      setParticipantIds(
        (meetingDetail.participants ?? []).map((p) => p.employee_id),
      );
    } else if (!meeting) {
      setTitle("");
      setMeetingDate("");
      setMeetingTime("");
      setLocation("");
      setMeetingType("ordinaire");
      setParticipantIds([]);
    }
  }, [meeting, meetingDetail, open]);

  const createMutation = useMutation({
    mutationFn: (data: MeetingCreate) => createMeeting(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "meetings"] });
      toast({
        title: "Réunion créée",
        description: "La réunion a été créée avec succès.",
      });
      onOpenChange(false);
    },
    onError: (error: unknown) => {
      const msg =
        error && typeof error === "object" && "message" in error
          ? String((error as { message?: string }).message)
          : "Erreur lors de la création";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({
      meetingId,
      data,
    }: {
      meetingId: string;
      data: MeetingUpdate;
    }) => {
      const updated = await updateMeeting(meetingId, data);
      const existingIds = new Set(
        (meetingDetail?.participants ?? []).map((p) => p.employee_id),
      );
      const toAdd = participantIds.filter((id) => !existingIds.has(id));
      if (toAdd.length > 0) {
        await addMeetingParticipants(meetingId, { employee_ids: toAdd });
      }
      return updated;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "meetings"] });
      queryClient.invalidateQueries({ queryKey: ["cse", "meeting-detail"] });
      toast({
        title: "Réunion mise à jour",
        description: "La réunion a été modifiée avec succès.",
      });
      onOpenChange(false);
    },
    onError: (error: unknown) => {
      const msg =
        error && typeof error === "object" && "message" in error
          ? String((error as { message?: string }).message)
          : "Erreur lors de la mise à jour";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    },
  });

  const toggleParticipant = (employeeId: string) => {
    setParticipantIds((prev) =>
      prev.includes(employeeId)
        ? prev.filter((id) => id !== employeeId)
        : [...prev, employeeId],
    );
  };

  const handleSubmit = () => {
    if (!title || !meetingDate) {
      toast({
        title: "Champs requis",
        description: "Le titre et la date sont obligatoires",
        variant: "destructive",
      });
      return;
    }

    if (meeting) {
      updateMutation.mutate({
        meetingId: meeting.id,
        data: {
          title,
          meeting_date: meetingDate,
          meeting_time: meetingTime || null,
          location: location || null,
          meeting_type: meetingType,
        },
      });
    } else {
      createMutation.mutate({
        title,
        meeting_date: meetingDate,
        meeting_time: meetingTime || undefined,
        location: location || undefined,
        meeting_type: meetingType,
        participant_ids: participantIds.length > 0 ? participantIds : undefined,
      });
    }
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {meeting ? "Modifier la réunion" : "Nouvelle réunion CSE"}
          </DialogTitle>
        </DialogHeader>
        {meeting && loadingDetail ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <Label htmlFor="title">Titre *</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Ex : Réunion CSE mensuelle"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="date">Date *</Label>
                <Input
                  id="date"
                  type="date"
                  value={meetingDate}
                  onChange={(e) => setMeetingDate(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="time">Heure</Label>
                <Input
                  id="time"
                  type="time"
                  value={meetingTime}
                  onChange={(e) => setMeetingTime(e.target.value)}
                />
              </div>
            </div>
            <div>
              <Label htmlFor="location">Lieu / Lien visio</Label>
              <Input
                id="location"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Ex : Salle de réunion A ou lien Zoom"
              />
            </div>
            <div>
              <Label htmlFor="type">Type de réunion *</Label>
              <Select
                value={meetingType}
                onValueChange={(v: typeof meetingType) => setMeetingType(v)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(MEETING_TYPE_LABELS) as Array<keyof typeof MEETING_TYPE_LABELS>).map(
                    (key) => (
                      <SelectItem key={key} value={key}>
                        {MEETING_TYPE_LABELS[key]}
                      </SelectItem>
                    ),
                  )}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Participants (élus CSE)</Label>
              <ScrollArea className="h-40 rounded-md border mt-2 p-3">
                {electedMembers.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Aucun élu actif.</p>
                ) : (
                  <div className="space-y-2">
                    {electedMembers.map((m) => (
                      <label
                        key={m.employee_id}
                        className="flex items-center gap-2 text-sm cursor-pointer"
                      >
                        <Checkbox
                          checked={participantIds.includes(m.employee_id)}
                          onCheckedChange={() => toggleParticipant(m.employee_id)}
                        />
                        <span>
                          {m.first_name} {m.last_name}
                          <span className="text-muted-foreground ml-1">
                            ({m.role})
                          </span>
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </ScrollArea>
              <p className="text-xs text-muted-foreground mt-1">
                {participantIds.length} participant{participantIds.length > 1 ? "s" : ""}{" "}
                sélectionné{participantIds.length > 1 ? "s" : ""}
              </p>
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isPending || (meeting && loadingDetail)}
          >
            {isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            {meeting ? "Modifier" : "Créer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
