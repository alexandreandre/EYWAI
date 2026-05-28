import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import {
  submitEvaluation,
  uploadEnrollmentCertificate,
  type TrainingCatalog,
  type TrainingEnrollment,
} from "@/api/training";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { enrollmentRejectionMessage } from "@/lib/employeeFormationUtils";

import {
  TRAINING_TYPE_LABELS,
  enrollmentStatusBadge,
  fmtDate,
  trainingAllowsFeedback,
} from "./employeeFormationFormatters";

function StarsReadonly({ value }: { value: number }) {
  const v = Math.round(value);
  return (
    <div className="flex gap-0.5 text-lg leading-none" aria-hidden>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={i <= v ? "text-amber-500" : "text-muted-foreground/25"}>
          ★
        </span>
      ))}
    </div>
  );
}

export function FormationEnrollmentCard({
  e,
  cat,
  companyId,
  employeeId,
}: {
  e: TrainingEnrollment;
  cat: TrainingCatalog | undefined;
  companyId: string;
  employeeId: string;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [hoverStar, setHoverStar] = useState<number | null>(null);
  const [pickedRating, setPickedRating] = useState<number | null>(null);
  const [evalComment, setEvalComment] = useState("");

  const showExtras = trainingAllowsFeedback(e.status);
  const hasRating = e.rating != null && e.rating >= 1;
  const displayPick = hoverStar ?? pickedRating;
  const rejectionMsg = enrollmentRejectionMessage(e);
  const isDone = showExtras;
  const needsCertificate = isDone && !e.certificate_url;
  const needsRating = isDone && !hasRating;

  const evalMut = useMutation({
    mutationFn: () => {
      const r = pickedRating;
      if (r == null || r < 1) throw new Error("note");
      return submitEvaluation(e.id, companyId, {
        rating: r,
        comment: evalComment.trim() || undefined,
      });
    },
    onSuccess: () => {
      toast({ title: "Merci — votre évaluation a bien été enregistrée." });
      setPickedRating(null);
      setEvalComment("");
      void queryClient.invalidateQueries({ queryKey: ["formation-enrollments", employeeId] });
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Impossible d'enregistrer l'évaluation.";
      toast({ title: "Erreur", description: String(detail), variant: "destructive" });
    },
  });

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadEnrollmentCertificate(e.id, companyId, file),
    onSuccess: () => {
      toast({ title: "Certificat enregistré" });
      void queryClient.invalidateQueries({ queryKey: ["formation-enrollments", employeeId] });
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Échec de l'envoi du fichier.";
      toast({ title: "Erreur", description: String(detail), variant: "destructive" });
    },
  });

  const typeLabel = cat?.training_type
    ? TRAINING_TYPE_LABELS[cat.training_type] ?? cat.training_type
    : "—";

  return (
    <Card className={needsRating || needsCertificate ? "border-primary/40" : undefined}>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">{e.training_title ?? cat?.title ?? "—"}</CardTitle>
            <CardDescription className="mt-1 flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{typeLabel}</Badge>
              {enrollmentStatusBadge(e.status)}
            </CardDescription>
          </div>
          <div className="text-right text-sm text-muted-foreground">
            {e.planned_date ? <p>Prévu : {fmtDate(e.planned_date)}</p> : null}
            {e.completion_date ? <p>Réalisé le : {fmtDate(e.completion_date)}</p> : null}
          </div>
        </div>
        {rejectionMsg ? (
          <p className="mt-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <span className="font-medium">Motif du refus : </span>
            {rejectionMsg}
          </p>
        ) : null}
        {e.notes?.trim() ? (
          <p className="mt-2 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Note RH : </span>
            {e.notes}
          </p>
        ) : null}
        {(needsRating || needsCertificate) && (
          <p className="mt-2 text-sm font-medium text-primary">
            {needsRating && needsCertificate
              ? "Action requise : évaluez cette formation et déposez votre certificat."
              : needsRating
                ? "Action requise : évaluez cette formation."
                : "Action requise : déposez votre certificat."}
          </p>
        )}
      </CardHeader>
      {showExtras ? (
        <CardContent className="space-y-6 border-t pt-4">
          <div className="space-y-3">
            <h3 className="text-sm font-semibold">Évaluation</h3>
            {!hasRating ? (
              <>
                <p className="text-sm text-muted-foreground">Évaluer cette formation</p>
                <div
                  className="flex gap-1"
                  onMouseLeave={() => setHoverStar(null)}
                  role="group"
                  aria-label="Note sur 5"
                >
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button
                      key={n}
                      type="button"
                      className={`rounded p-0.5 text-2xl leading-none transition-colors ${
                        displayPick != null && n <= displayPick
                          ? "text-amber-500"
                          : "text-muted-foreground/25"
                      } hover:text-amber-400`}
                      onMouseEnter={() => setHoverStar(n)}
                      onClick={() => setPickedRating(n)}
                      aria-label={`${n} sur 5`}
                    >
                      ★
                    </button>
                  ))}
                </div>
                <Textarea
                  placeholder="Commentaire (optionnel)"
                  value={evalComment}
                  onChange={(ev) => setEvalComment(ev.target.value)}
                  rows={3}
                  className="max-w-lg"
                />
                <Button
                  type="button"
                  size="sm"
                  disabled={evalMut.isPending || pickedRating == null || pickedRating < 1}
                  onClick={() => evalMut.mutate()}
                >
                  {evalMut.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Envoi…
                    </>
                  ) : (
                    "Envoyer mon évaluation"
                  )}
                </Button>
              </>
            ) : (
              <div className="space-y-2">
                <StarsReadonly value={e.rating ?? 0} />
                {e.evaluation_comment ? (
                  <p className="text-sm text-foreground">{e.evaluation_comment}</p>
                ) : null}
                <p className="text-xs text-muted-foreground">
                  Évaluée le {e.evaluated_at ? fmtDate(e.evaluated_at) : "—"}
                </p>
              </div>
            )}
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-semibold">Certificat</h3>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
              className="sr-only"
              onChange={(ev) => {
                const f = ev.target.files?.[0];
                ev.target.value = "";
                if (f) uploadMut.mutate(f);
              }}
            />
            {e.certificate_url ? (
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" size="sm" asChild>
                  <a href={e.certificate_url} target="_blank" rel="noopener noreferrer">
                    Télécharger mon certificat
                  </a>
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={uploadMut.isPending}
                  onClick={() => fileRef.current?.click()}
                >
                  {uploadMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Remplacer"}
                </Button>
              </div>
            ) : (
              <Button
                type="button"
                variant={needsCertificate ? "default" : "outline"}
                size="sm"
                disabled={uploadMut.isPending}
                onClick={() => fileRef.current?.click()}
              >
                {uploadMut.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Envoi…
                  </>
                ) : (
                  "Uploader mon certificat"
                )}
              </Button>
            )}
          </div>
        </CardContent>
      ) : null}
    </Card>
  );
}
