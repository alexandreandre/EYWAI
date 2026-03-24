// frontend/src/components/AnnualReviewForm.tsx
// Formulaire de saisie RH pour la fiche d'entretien

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Save } from "lucide-react";
import type { AnnualReview, AnnualReviewUpdate } from "@/api/annualReviews";

interface AnnualReviewFormProps {
  review: AnnualReview;
  onSave: (data: AnnualReviewUpdate) => Promise<void>;
  onClose?: () => void;
  isLoading?: boolean;
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSave(formData);
  };

  const handleChange = (field: keyof AnnualReviewUpdate, value: string | null) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Compte-rendu d'entretien</CardTitle>
          <CardDescription>Compte-rendu rédigé après la réalisation de l'entretien</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
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
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Résumé de l'évaluation</CardTitle>
          <CardDescription>Synthèse générale de l'entretien</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="evaluation_summary">Résumé de l'évaluation</Label>
            <Textarea
              id="evaluation_summary"
              value={formData.evaluation_summary || ""}
              onChange={(e) => handleChange("evaluation_summary", e.target.value)}
              rows={4}
              placeholder="Résumé général de l'entretien..."
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="rh_notes">Notes RH</Label>
            <Textarea
              id="rh_notes"
              value={formData.rh_notes || ""}
              onChange={(e) => handleChange("rh_notes", e.target.value)}
              rows={3}
              placeholder="Notes complémentaires..."
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Objectifs</CardTitle>
          <CardDescription>Objectifs atteints et fixés</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
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
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Points forts et axes d'amélioration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
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
            <Label htmlFor="improvement_areas">Axes d'amélioration</Label>
            <Textarea
              id="improvement_areas"
              value={formData.improvement_areas || ""}
              onChange={(e) => handleChange("improvement_areas", e.target.value)}
              rows={4}
              placeholder="Axes d'amélioration identifiés..."
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Développement professionnel</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
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
              placeholder="Perspectives de carrière et évolution professionnelle..."
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Évaluation et suivi</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
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
            <Label htmlFor="overall_rating">Note globale</Label>
            <Input
              id="overall_rating"
              value={formData.overall_rating || ""}
              onChange={(e) => handleChange("overall_rating", e.target.value)}
              placeholder="Ex: Très satisfaisant, Satisfaisant, À améliorer..."
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-2 justify-end">
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
    </form>
  );
}
