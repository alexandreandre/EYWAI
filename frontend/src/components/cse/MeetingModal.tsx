// frontend/src/components/cse/MeetingModal.tsx
// Modal pour créer/éditer une réunion CSE

import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import {
  createMeeting,
  updateMeeting,
  type MeetingCreate,
  type MeetingUpdate,
  type MeetingListItem,
} from "@/api/cse";
import { Loader2 } from "lucide-react";

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
  const [meetingType, setMeetingType] = useState<"ordinaire" | "extraordinaire" | "cssct" | "autre">("ordinaire");
  const [participantIds, setParticipantIds] = useState<string[]>([]);

  useEffect(() => {
    if (meeting) {
      setTitle(meeting.title);
      setMeetingDate(meeting.meeting_date.split('T')[0]);
      setMeetingTime(meeting.meeting_time || "");
      setMeetingType(meeting.meeting_type);
    } else {
      setTitle("");
      setMeetingDate("");
      setMeetingTime("");
      setLocation("");
      setMeetingType("ordinaire");
      setParticipantIds([]);
    }
  }, [meeting, open]);

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
    onError: (error: any) => {
      toast({
        title: "Erreur",
        description: error.message || "Erreur lors de la création",
        variant: "destructive",
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ meetingId, data }: { meetingId: string; data: MeetingUpdate }) =>
      updateMeeting(meetingId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "meetings"] });
      toast({
        title: "Réunion mise à jour",
        description: "La réunion a été modifiée avec succès.",
      });
      onOpenChange(false);
    },
    onError: (error: any) => {
      toast({
        title: "Erreur",
        description: error.message || "Erreur lors de la mise à jour",
        variant: "destructive",
      });
    },
  });

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
        participant_ids: participantIds,
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {meeting ? "Modifier la réunion" : "Nouvelle réunion CSE"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="title">Titre *</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Ex: Réunion CSE mensuelle"
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
              placeholder="Ex: Salle de réunion A ou lien Zoom"
            />
          </div>
          <div>
            <Label htmlFor="type">Type de réunion *</Label>
            <Select value={meetingType} onValueChange={(v: any) => setMeetingType(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ordinaire">Ordinaire</SelectItem>
                <SelectItem value="extraordinaire">Extraordinaire</SelectItem>
                <SelectItem value="cssct">CSSCT</SelectItem>
                <SelectItem value="autre">Autre</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {/* Note: La sélection des participants sera ajoutée dans une version future */}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={createMutation.isPending || updateMutation.isPending}
          >
            {(createMutation.isPending || updateMutation.isPending) && (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            )}
            {meeting ? "Modifier" : "Créer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
