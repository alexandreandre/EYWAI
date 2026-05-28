import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, Mic, Square, Trash2, X } from "lucide-react";
import { uploadNoteAudio } from "@/api/recruitment";
import { createBlobPreviewUrl } from "@/lib/downloadBlob";

export type NoteRecorderUiState = "idle" | "recording" | "recorded" | "uploading";

export const NOTE_AUDIO_MAX_SECONDS = 300;

export function formatNoteRecSecs(total: number): string {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function CandidateNoteAudioRecorder({
  candidateId,
  companyId,
  audioUrl,
  onAudioUrl,
  disabled,
}: {
  candidateId: string;
  companyId: string;
  audioUrl: string | null;
  onAudioUrl: (url: string | null) => void;
  disabled?: boolean;
}) {
  const { toast } = useToast();
  const [ui, setUi] = useState<NoteRecorderUiState>("idle");
  const [seconds, setSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const previewUrlRef = useRef<string | null>(null);
  const recordedBlobRef = useRef<Blob | null>(null);
  const elapsedRef = useRef(0);

  const stopTimer = () => {
    if (timerRef.current != null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const cleanupStream = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  };

  const revokePreview = () => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
  };

  useEffect(
    () => () => {
      stopTimer();
      cleanupStream();
      revokePreview();
      mediaRecorderRef.current = null;
    },
    [],
  );

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      let mime = "audio/webm";
      if (typeof MediaRecorder !== "undefined" && !MediaRecorder.isTypeSupported("audio/webm")) {
        if (MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")) {
          mime = "audio/ogg;codecs=opus";
        } else {
          mime = "";
        }
      }
      const options: MediaRecorderOptions | undefined = mime ? { mimeType: mime } : undefined;
      const mr = new MediaRecorder(stream, options);
      chunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mr.onstop = () => {
        stopTimer();
        cleanupStream();
        const blobType = mr.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: blobType });
        recordedBlobRef.current = blob;
        revokePreview();
        const url = createBlobPreviewUrl(blob);
        previewUrlRef.current = url;
        setUi("recorded");
      };
      mediaRecorderRef.current = mr;
      elapsedRef.current = 0;
      setSeconds(0);
      setUi("recording");
      mr.start(1000);
      timerRef.current = setInterval(() => {
        elapsedRef.current += 1;
        setSeconds(elapsedRef.current);
        if (elapsedRef.current >= NOTE_AUDIO_MAX_SECONDS) {
          mr.stop();
        }
      }, 1000);
    } catch {
      toast({
        title: "Permission micro refusée",
        description: "Autorisez l'accès au microphone pour enregistrer une note audio.",
        variant: "destructive",
      });
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
  };

  const discardRecording = () => {
    revokePreview();
    recordedBlobRef.current = null;
    elapsedRef.current = 0;
    setSeconds(0);
    setUi("idle");
  };

  const confirmUpload = async () => {
    const blob = recordedBlobRef.current;
    if (!blob) return;
    setUi("uploading");
    try {
      const { audio_url } = await uploadNoteAudio(candidateId, companyId, blob);
      onAudioUrl(audio_url);
      revokePreview();
      recordedBlobRef.current = null;
      elapsedRef.current = 0;
      setSeconds(0);
      setUi("idle");
    } catch {
      toast({
        title: "Erreur",
        description: "Impossible d'envoyer l'enregistrement.",
        variant: "destructive",
      });
      setUi("recorded");
    }
  };

  if (audioUrl) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Badge className="bg-emerald-600 gap-1 font-normal">
          Audio joint
        </Badge>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-7 w-7 shrink-0"
          aria-label="Retirer l'audio"
          disabled={disabled}
          onClick={() => onAudioUrl(null)}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
    );
  }

  if (ui === "uploading") {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Envoi de l&apos;audio…
      </div>
    );
  }

  if (ui === "recording") {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex items-center gap-1.5 text-xs font-medium text-red-600">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-red-600" />
          </span>
          Enregistrement
        </span>
        <span className="text-sm tabular-nums text-muted-foreground">{formatNoteRecSecs(seconds)}</span>
        <Button
          type="button"
          size="sm"
          variant="destructive"
          className="h-8 gap-1"
          onClick={stopRecording}
        >
          <Square className="h-3.5 w-3.5 fill-current" />
          Stop
        </Button>
      </div>
    );
  }

  if (ui === "recorded" && previewUrlRef.current) {
    return (
      <div className="space-y-2 rounded-md border bg-background/80 p-2">
        <audio src={previewUrlRef.current} controls className="h-8 w-full max-w-md" />
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" className="h-8 gap-1" onClick={discardRecording}>
            <Trash2 className="h-3.5 w-3.5" />
            Supprimer
          </Button>
          <Button type="button" size="sm" className="h-8" onClick={confirmUpload} disabled={disabled}>
            Utiliser cet enregistrement
          </Button>
        </div>
      </div>
    );
  }

  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      className="h-8 gap-1"
      disabled={disabled}
      onClick={startRecording}
    >
      <Mic className="h-3.5 w-3.5" />
      Enregistrer un audio
    </Button>
  );
}
