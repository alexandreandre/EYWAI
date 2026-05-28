import { TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import type { EmployeeFormationTabId } from "@/lib/employeeFormationUtils";
import type { FormationSummaryCounts } from "@/hooks/useEmployeeFormationSummary";

type TabDef = {
  id: EmployeeFormationTabId;
  label: string;
  shortLabel?: string;
  group: "parcours" | "formation" | "integration";
};

const TAB_DEFS: TabDef[] = [
  { id: "entretiens", label: "Mes entretiens", shortLabel: "Entretiens", group: "parcours" },
  { id: "objectifs", label: "Mes objectifs", shortLabel: "Objectifs", group: "parcours" },
  { id: "competences", label: "Mes compétences", shortLabel: "Compétences", group: "parcours" },
  { id: "formations", label: "Mes formations", shortLabel: "Formations", group: "formation" },
  { id: "habilitations", label: "Mes habilitations", shortLabel: "Habilit.", group: "formation" },
  { id: "obligations", label: "Obligations légales", shortLabel: "Obligations", group: "formation" },
  { id: "onboarding", label: "Mon onboarding", shortLabel: "Onboarding", group: "integration" },
];

const GROUP_LABELS: Record<TabDef["group"], string> = {
  parcours: "Parcours",
  formation: "Formation & conformité",
  integration: "Intégration",
};

function tabBadgeCount(id: EmployeeFormationTabId, counts: FormationSummaryCounts): number {
  if (id === "entretiens") return counts.reviewsAction;
  if (id === "formations") return counts.enrollmentsPending;
  if (id === "habilitations") return counts.certsWatch;
  if (id === "onboarding" && counts.onboardingIncomplete) return 1;
  return 0;
}

export function EmployeeFormationTabs({ counts }: { counts: FormationSummaryCounts }) {
  const groups: TabDef["group"][] = ["parcours", "formation", "integration"];

  return (
    <div className="mb-4 space-y-3">
      {groups.map((group) => {
        const tabs = TAB_DEFS.filter((t) => t.group === group);
        return (
          <div key={group} className="space-y-1.5">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {GROUP_LABELS[group]}
            </p>
            <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1 bg-transparent p-0">
              {tabs.map((tab) => {
                const badge = tabBadgeCount(tab.id, counts);
                return (
                  <TabsTrigger
                    key={tab.id}
                    value={tab.id}
                    className={cn(
                      "data-[state=active]:bg-background data-[state=active]:shadow-sm",
                      "border border-transparent data-[state=active]:border-border",
                    )}
                  >
                    <span className="hidden sm:inline">{tab.label}</span>
                    <span className="sm:hidden">{tab.shortLabel ?? tab.label}</span>
                    {badge > 0 && (
                      <span className="ml-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground">
                        {badge}
                      </span>
                    )}
                  </TabsTrigger>
                );
              })}
            </TabsList>
          </div>
        );
      })}
    </div>
  );
}
