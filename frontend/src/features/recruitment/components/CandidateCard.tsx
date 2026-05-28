import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { isRecruitmentPriorityCandidate, type Candidate } from "@/api/recruitment";
import { cn } from "@/lib/utils";
import { recruitmentAiPalette } from "./recruitmentUtils";

export function CandidateCard({
  candidate,
  onClick,
  jobTitle,
}: {
  candidate: Candidate;
  onClick: () => void;
  jobTitle?: string | null;
}) {
  const ai = candidate.ai_score;
  const pal = ai != null ? recruitmentAiPalette(ai) : null;
  const isPriority = isRecruitmentPriorityCandidate(candidate);
  return (
    <div
      onClick={onClick}
      className={cn(
        "relative w-full bg-white border rounded-lg p-3 cursor-pointer hover:shadow-md transition-shadow group",
        ai != null && "pb-7",
        isPriority && "ring-1 ring-amber-300/80",
      )}
    >
      <div className="flex items-start gap-2">
        <Avatar className="h-8 w-8 flex-shrink-0 mt-0.5">
          <AvatarFallback className="text-xs bg-primary/10 text-primary font-medium">
            {candidate.first_name[0]}{candidate.last_name[0]}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1">
            <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
              {candidate.first_name} {candidate.last_name}
            </p>
            {isPriority ? (
              <Badge variant="outline" className="text-[9px] h-4 px-1 border-amber-400 text-amber-800 bg-amber-50 shrink-0">
                Entretien RH
              </Badge>
            ) : null}
          </div>
          {candidate.email && (
            <p className="text-xs text-muted-foreground truncate">{candidate.email}</p>
          )}
          {jobTitle ? (
            <Badge variant="secondary" className="mt-0.5 text-[9px] h-4 px-1 max-w-full truncate">
              {jobTitle}
            </Badge>
          ) : null}
          <p className="text-[10px] text-muted-foreground mt-0.5">
            Depuis le {new Date(candidate.created_at).toLocaleDateString("fr-FR")}
          </p>
          {candidate.source && (
            <Badge variant="outline" className="mt-1 text-[10px] h-5">{candidate.source}</Badge>
          )}
        </div>
      </div>
      {ai != null && pal ? (
        <span
          className={cn(
            "pointer-events-none absolute bottom-1.5 right-1.5 rounded border px-1.5 py-0.5 text-[10px] font-bold tabular-nums",
            pal.badge,
          )}
          aria-label={`Score IA ${ai}`}
        >
          {ai}
        </span>
      ) : null}
    </div>
  );
}
