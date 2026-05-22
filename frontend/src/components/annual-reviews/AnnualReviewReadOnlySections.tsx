import type { AnnualReview } from "@/api/annualReviews";
import { Badge } from "@/components/ui/badge";
import { buildAnnualReviewReadOnlySections } from "@/lib/annualReviewFormUtils";
import { cn } from "@/lib/utils";

interface AnnualReviewReadOnlySectionsProps {
  review: AnnualReview;
  className?: string;
}

export function AnnualReviewReadOnlySections({
  review,
  className,
}: AnnualReviewReadOnlySectionsProps) {
  const sections = buildAnnualReviewReadOnlySections(review);

  return (
    <div className={cn("space-y-4", className)}>
      {sections.map((section) => {
        const filled =
          section.value != null &&
          (typeof section.value !== "string" || section.value.trim().length > 0);

        return (
          <div
            key={section.id}
            className="rounded-lg border bg-card p-4"
          >
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-foreground">{section.title}</h3>
              <Badge
                variant="outline"
                className={cn(
                  "font-normal text-xs",
                  filled
                    ? "border-success/30 bg-success/10 text-success"
                    : "border-muted-foreground/30 bg-muted text-muted-foreground"
                )}
              >
                {filled ? "Renseigné" : "À compléter"}
              </Badge>
            </div>
            {filled ? (
              <p
                className={cn(
                  "text-sm whitespace-pre-wrap leading-relaxed text-foreground",
                  section.id === "overall_rating" && "text-lg font-semibold text-primary"
                )}
              >
                {section.value}
              </p>
            ) : (
              <p className="text-sm italic text-muted-foreground">Non renseigné</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
