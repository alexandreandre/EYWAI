// frontend/src/components/EmployeeCSEBlock.tsx
// Bloc CSE compact à afficher dans la fiche salarié (RH uniquement)

import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Link } from "react-router-dom";
import { CSEBadge } from "@/components/CSEBadge";
import {
  getElectedMembers,
  getDelegationQuota,
  getDelegationHours,
  getMeetings,
} from "@/api/cse";
import { Users, Calendar, Clock, ArrowRight, Loader2 } from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";
import { cn } from "@/lib/utils";

interface EmployeeCSEBlockProps {
  employeeId: string;
  /** Champs enrichis depuis FullEmployee (backend) — affichés si présents. */
  collegeElectoral?: string | null;
  statutCse?: string | null;
  heuresDelegationMensuelles?: number | null;
}

const BANNER_CLASS =
  "rounded-md border border-blue-200/80 bg-blue-50/80 px-3 py-2 text-xs text-blue-950 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100";

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

function InfoSep() {
  return (
    <span className="hidden sm:inline text-blue-300/80 dark:text-blue-700" aria-hidden>
      ·
    </span>
  );
}

export function EmployeeCSEBlock({
  employeeId,
  collegeElectoral,
  statutCse,
  heuresDelegationMensuelles,
}: EmployeeCSEBlockProps) {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id;

  const { data: members = [], isLoading: loadingMandate } = useQuery({
    queryKey: ["cse", "elected-members"],
    queryFn: () => getElectedMembers(true),
    enabled: !!companyId,
  });

  const mandate = members.find((m) => m.employee_id === employeeId);

  const { data: quota } = useQuery({
    queryKey: ["cse", "delegation-quota", employeeId],
    queryFn: () => getDelegationQuota(employeeId),
    enabled: !!mandate && !!employeeId,
  });

  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split("T")[0];
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split("T")[0];

  const { data: hours = [] } = useQuery({
    queryKey: ["cse", "delegation-hours", employeeId, monthStart, monthEnd],
    queryFn: () => getDelegationHours(employeeId, monthStart, monthEnd),
    enabled: !!mandate && !!employeeId,
  });

  const { data: meetings = [] } = useQuery({
    queryKey: ["cse", "meetings", "upcoming"],
    queryFn: () => getMeetings("a_venir"),
    enabled: !!mandate,
  });

  if (!loadingMandate && !mandate) {
    return null;
  }

  const nextMeeting = meetings.length > 0 ? meetings[0] : null;

  const consumedHours = hours.reduce((sum, h) => sum + h.duration_hours, 0);
  const quotaHours = quota?.quota_hours_per_month || 0;
  const remainingHours = quotaHours - consumedHours;

  if (loadingMandate) {
    return (
      <div className={cn(BANNER_CLASS, "flex items-center gap-2")}>
        <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
        <span className="text-muted-foreground">Chargement CSE…</span>
      </div>
    );
  }

  if (!mandate) {
    return null;
  }

  const daysRemaining = mandate.end_date
    ? Math.ceil(
        (new Date(mandate.end_date).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24),
      )
    : null;

  const ficheExtras = [
    collegeElectoral ? `Collège : ${collegeElectoral}` : null,
    statutCse ? `Statut fiche : ${statutCse}` : null,
    heuresDelegationMensuelles != null
      ? `Délégation (fiche) : ${heuresDelegationMensuelles} h/mois`
      : null,
  ].filter(Boolean) as string[];

  return (
    <div className={BANNER_CLASS}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Users className="h-3.5 w-3.5 shrink-0 text-blue-600 dark:text-blue-400" aria-hidden />
        <span className="font-semibold shrink-0">CSE & Dialogue Social</span>
        <CSEBadge
          role={mandate.role}
          college={mandate.college}
          startDate={mandate.start_date}
          endDate={mandate.end_date}
          daysRemaining={daysRemaining}
          compact
        />

        <InfoSep />
        <span className="inline-flex flex-wrap items-center gap-1 text-blue-900/90 dark:text-blue-100/90">
          <Calendar className="h-3 w-3 shrink-0 opacity-70" aria-hidden />
          <span>
            Mandat {formatDate(mandate.start_date)} → {formatDate(mandate.end_date)}
          </span>
          {daysRemaining !== null && (
            <Badge
              variant={daysRemaining <= 90 ? "destructive" : "secondary"}
              className="h-5 px-1.5 text-[10px] font-medium"
            >
              {daysRemaining > 0
                ? `${daysRemaining} j restant${daysRemaining > 1 ? "s" : ""}`
                : "Expiré"}
            </Badge>
          )}
        </span>

        {quota ? (
          <>
            <InfoSep />
            <span className="inline-flex flex-wrap items-center gap-1 text-blue-900/90 dark:text-blue-100/90">
              <Clock className="h-3 w-3 shrink-0 opacity-70" aria-hidden />
              <span>
                Délégation {consumedHours.toFixed(1)}/{quotaHours} h
              </span>
              <Badge
                variant={
                  remainingHours < 0
                    ? "destructive"
                    : remainingHours <= quotaHours * 0.2
                      ? "secondary"
                      : "default"
                }
                className="h-5 px-1.5 text-[10px] font-medium"
              >
                {remainingHours.toFixed(1)} h restantes
              </Badge>
            </span>
          </>
        ) : null}

        {nextMeeting ? (
          <>
            <InfoSep />
            <span className="inline-flex flex-wrap items-center gap-1 text-blue-900/90 dark:text-blue-100/90">
              <span className="font-medium">Prochaine réunion</span>
              <span>{formatDate(nextMeeting.meeting_date)}</span>
              <span className="text-blue-800/70 dark:text-blue-200/70">— {nextMeeting.title}</span>
            </span>
          </>
        ) : null}

        <Link
          to="/cse"
          className="ml-auto inline-flex items-center gap-1 font-medium text-blue-700 hover:text-blue-900 dark:text-blue-300 dark:hover:text-blue-100 shrink-0"
        >
          Module CSE
          <ArrowRight className="h-3 w-3" aria-hidden />
        </Link>
      </div>

      {ficheExtras.length > 0 ? (
        <p className="mt-1.5 text-[11px] leading-snug text-blue-800/75 dark:text-blue-200/75">
          {ficheExtras.join(" · ")}
        </p>
      ) : null}
    </div>
  );
}
