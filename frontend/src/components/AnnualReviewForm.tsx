// frontend/src/components/AnnualReviewForm.tsx
// Formulaire de saisie RH pour la fiche d'entretien

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, Save } from "lucide-react";
import type { AnnualReview, AnnualReviewUpdate } from "@/api/annualReviews";
import {
  annualReviewFormCompletionPercent,
  isPresetOverallRating,
  OVERALL_RATING_PRESETS,
} from "@/lib/annualReviewFormUtils";

interface AnnualReviewFormProps {
  review: AnnualReview;
  onSave: (data: AnnualReviewUpdate) => Promise<void>;
  onClose?: () => void;
  isLoading?: boolean;
}

function toDateInputValue(value: string | null | undefined): string {
  if (!value) return "";
  return value.includes("T") ? value.slice(0, 10) : value;
}

export function AnnualReviewForm({
  review,
  onSave,
  onClose,
  isLoading = false,
}: AnnualReviewFormProps) {
  const [formData, setFormData] = useState<AnnualReviewUpdate>({
    meeting_report: review.meeting_report || "",
    rh_notes: review.rh_notes || "",
    evaluation_summary: review.evaluation_summary || "",
    objectives_achieved: review.objectives_achieved || "",
    objectives_next_year: review.objectives_next_year || "",
    strengths: review.strengths || "",
    improvement_areas: review.improvement_areas || "",
    training_needs: review.training_needs || "",
    career_development: review.career_development || "",
    salary_review: review.salary_review || "",
    overall_rating: review.overall_rating || "",
    next_review_date: review.next_review_date || null,
  });

  const [ratingMode, setRatingMode] = useState<"preset" | "custom">(() =>
    isPresetOverallRating(review.overall_rating) || !review.overall_rating
      ? "preset"
      : "custom"
  );

  const completionPreview = useMemo(
    () =>
      annualReviewFormCompletionPercent({
        ...review,
        meeting_report: formData.meeting_report ?? null,
        rh_notes: formData.rh_notes ?? null,
        evaluation_summary: formData.evaluation_summary ?? null,
        objectives_achieved: formData.objectives_achieved ?? null,
        objectives_next_year: formData.objectives_next_year ?? null,
        strengths: formData.strengths ?? null,
        improvement_areas: formData.improvement_areas ?? null,
        training_needs: formData.training_needs ?? null,
        career_development: formData.career_development ?? null,
        salary_review: formData.salary_review ?? null,
        overall_rating: formData.overall_rating ?? null,
        next_review_date: formData.next_review_date ?? null,
      }),
    [review, formData]
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSave(formData);
  };

  const handleChange = (field: keyof AnnualReviewUpdate, value: string | null) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <form onSubmit={handleSubmit} className="relative pb-20">
      <div className="mb-4 space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Complétion de la fiche</span>
          <span className="font-medium text-foreground">{completionPreview} %</span>
        </div>
        <Progress value={completionPreview} className="h-2" />
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Compte-rendu d&apos;entretien</CardTitle>
          <CardDescription>Synthèse rédigée après la tenue de l&apos;entretien</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="meeting_report">Compte-rendu</Label>
            <Textarea
              id="meeting_report"
              value={formData.meeting_report || ""}
              onChange={(e) => handleChange("meeting_report", e.target.value)}
              rows={6}
              placeholder="Rédigez le compte-rendu de l'entretien..."
            />
          </div>

          <Separator />

          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-foreground">Évaluation</h3>
            <div className="space-y-2">
              <Label htmlFor="evaluation_summary">Résumé de l&apos;évaluation</Label>
              <Textarea
                id="evaluation_summary"
                value={formData.evaluation_summary || ""}
                onChange={(e) => handleChange("evaluation_summary", e.target.value)}
                rows={4}
                placeholder="Résumé général de l'entretien..."
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="rh_notes">Notes RH (internes à la fiche)</Label>
              <Textarea
                id="rh_notes"
                value={formData.rh_notes || ""}
                onChange={(e) => handleChange("rh_notes", e.target.value)}
                rows={3}
                placeholder="Notes complémentaires..."
              />
            </div>
          </div>

          <Separator />

          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-foreground">Objectifs</h3>
            <div className="space-y-2">
              <Label htmlFor="objectives_achieved">Objectifs atteints</Label>
              <Textarea
                id="objectives_achieved"
                value={formData.objectives_achieved || ""}
                onChange={(e) => handleChange("objectives_achieved", e.target.value)}
                rows={4}
                placeholder="Objectifs atteints..."
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="objectives_next_year">Objectifs futurs</Label>
              <Textarea
                id="objectives_next_year"
                value={formData.objectives_next_year || ""}
                onChange={(e) => handleChange("objectives_next_year", e.target.value)}
                rows={4}
                placeholder="Objectifs fixés pour l'avenir..."
              />
            </div>
          </div>

          <Separator />

          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-foreground">Points forts et axes d&apos;amélioration</h3>
            <div className="space-y-2">
              <Label htmlFor="strengths">Points forts</Label>
              <Textarea
                id="strengths"
                value={formData.strengths || ""}
                onChange={(e) => handleChange("strengths", e.target.value)}
                rows={4}
                placeholder="Points forts identifiés..."
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="improvement_areas">Axes d&apos;amélioration</Label>
              <Textarea
                id="improvement_areas"
                value={formData.improvement_areas || ""}
                onChange={(e) => handleChange("improvement_areas", e.target.value)}
                rows={4}
                placeholder="Axes d'amélioration identifiés..."
              />
            </div>
          </div>

          <Separator />

          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-foreground">Développement professionnel</h3>
            <div className="space-y-2">
              <Label htmlFor="training_needs">Besoins en formation</Label>
              <Textarea
                id="training_needs"
                value={formData.training_needs || ""}
                onChange={(e) => handleChange("training_needs", e.target.value)}
                rows={3}
                placeholder="Besoins en formation identifiés..."
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="career_development">Évolution professionnelle</Label>
              <Textarea
                id="career_development"
                value={formData.career_development || ""}
                onChange={(e) => handleChange("career_development", e.target.value)}
                rows={3}
                placeholder="Perspectives de carrière..."
              />
            </div>
          </div>

          <Separator />

          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-foreground">Évaluation finale et suivi</h3>
            <div className="space-y-2">
              <Label htmlFor="salary_review">Évolution salariale</Label>
              <Textarea
                id="salary_review"
                value={formData.salary_review || ""}
                onChange={(e) => handleChange("salary_review", e.target.value)}
                rows={2}
                placeholder="Évolution salariale discutée..."
              />
            </div>
            <div className="space-y-2">
              <Label>Note globale</Label>
              <Select
                value={ratingMode === "preset" ? formData.overall_rating || "" : "_custom"}
                onValueChange={(v) => {
                  if (v === "_custom") {
                    setRatingMode("custom");
                    if (isPresetOverallRating(formData.overall_rating)) {
                      handleChange("overall_rating", "");
                    }
                  } else {
                    setRatingMode("preset");
                    handleChange("overall_rating", v);
                  }
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Choisir une note..." />
                </SelectTrigger>
                <SelectContent>
                  {OVERALL_RATING_PRESETS.map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {opt}
                    </SelectItem>
                  ))}
                  <SelectItem value="_custom">Autre (saisie libre)</SelectItem>
                </SelectContent>
              </Select>
              {ratingMode === "custom" && (
                <Input
                  id="overall_rating"
                  value={formData.overall_rating || ""}
                  onChange={(e) => handleChange("overall_rating", e.target.value)}
                  placeholder="Saisir une note personnalisée..."
                  className="mt-2"
                />
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="next_review_date">Date du prochain entretien</Label>
              <Input
                id="next_review_date"
                type="date"
                value={toDateInputValue(formData.next_review_date)}
                onChange={(e) =>
                  handleChange("next_review_date", e.target.value ? e.target.value : null)
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="sticky bottom-0 z-10 -mx-1 mt-6 border-t bg-background/95 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex justify-end gap-2">
          {onClose && (
            <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
              Annuler
            </Button>
          )}
          <Button type="submit" disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Enregistrement...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Enregistrer
              </>
            )}
          </Button>
        </div>
      </div>
    </form>
  );
}
