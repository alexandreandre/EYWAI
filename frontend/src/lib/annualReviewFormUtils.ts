import type { AnnualReview } from "@/api/annualReviews";

/** Champs comptés pour l'indicateur de complétion de la fiche. */
export const ANNUAL_REVIEW_FORM_FIELDS: (keyof AnnualReview)[] = [
  "meeting_report",
  "evaluation_summary",
  "rh_notes",
  "objectives_achieved",
  "objectives_next_year",
  "strengths",
  "improvement_areas",
  "training_needs",
  "career_development",
  "salary_review",
  "overall_rating",
  "next_review_date",
];

export function annualReviewFormCompletionPercent(review: AnnualReview): number {
  const filled = ANNUAL_REVIEW_FORM_FIELDS.filter((key) => {
    const v = review[key];
    if (v == null) return false;
    if (typeof v === "string") return v.trim().length > 0;
    return true;
  }).length;
  return Math.round((filled / ANNUAL_REVIEW_FORM_FIELDS.length) * 100);
}

export const OVERALL_RATING_PRESETS = [
  "Exceptionnel",
  "Très satisfaisant",
  "Satisfaisant",
  "Partiellement satisfaisant",
  "À améliorer",
  "Insuffisant",
] as const;

export function isPresetOverallRating(value: string | null | undefined): boolean {
  if (!value) return false;
  return (OVERALL_RATING_PRESETS as readonly string[]).includes(value);
}

export interface ReadOnlySection {
  id: string;
  title: string;
  value: string | null | undefined;
}

export function buildAnnualReviewReadOnlySections(review: AnnualReview): ReadOnlySection[] {
  return [
    { id: "meeting_report", title: "Compte-rendu d'entretien", value: review.meeting_report },
    { id: "evaluation_summary", title: "Résumé de l'évaluation", value: review.evaluation_summary },
    { id: "rh_notes", title: "Notes RH", value: review.rh_notes },
    { id: "objectives_achieved", title: "Objectifs atteints", value: review.objectives_achieved },
    { id: "objectives_next_year", title: "Objectifs futurs", value: review.objectives_next_year },
    { id: "strengths", title: "Points forts", value: review.strengths },
    { id: "improvement_areas", title: "Axes d'amélioration", value: review.improvement_areas },
    { id: "training_needs", title: "Besoins en formation", value: review.training_needs },
    { id: "career_development", title: "Évolution professionnelle", value: review.career_development },
    { id: "salary_review", title: "Évolution salariale", value: review.salary_review },
    { id: "overall_rating", title: "Note globale", value: review.overall_rating },
    {
      id: "next_review_date",
      title: "Date du prochain entretien",
      value: review.next_review_date
        ? new Date(
            review.next_review_date.includes("T")
              ? review.next_review_date
              : `${review.next_review_date}T12:00:00`
          ).toLocaleDateString("fr-FR", {
            day: "2-digit",
            month: "long",
            year: "numeric",
          })
        : null,
    },
  ];
}

export function annualReviewStatusHelpMessage(status: AnnualReview["status"]): string {
  switch (status) {
    case "planifie":
      return "L'entretien est planifié. Envoyez les notes de préparation au salarié pour lancer l'acceptation.";
    case "en_attente_acceptation":
      return "En attente de l'acceptation du salarié. Vous pouvez encore modifier les notes de préparation.";
    case "accepte":
      return "Accepté par le salarié. Marquez l'entretien comme réalisé après la tenue de l'échange.";
    case "refuse":
      return "Refusé par le salarié. Contactez le collaborateur ou replanifiez l'entretien.";
    case "realise":
      return "Entretien réalisé. Complétez le compte-rendu puis clôturez pour générer le PDF.";
    case "cloture":
      return "Entretien clôturé. Vous pouvez télécharger le PDF et lancer la signature électronique.";
    default:
      return "";
  }
}
