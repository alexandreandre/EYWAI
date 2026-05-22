import { AlertCircle, CheckCircle2, ListTodo } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import type { OnboardingTaskStats } from "@/lib/onboardingUtils";

type OnboardingKpiBandProps = {
  stats: OnboardingTaskStats;
};

export function OnboardingKpiBand({ stats }: OnboardingKpiBandProps) {
  const tiles = [
    {
      label: "À faire",
      value: stats.todo,
      icon: ListTodo,
      iconClass: "text-blue-600",
      bgClass: "bg-blue-100",
    },
    {
      label: "En retard",
      value: stats.overdue,
      icon: AlertCircle,
      iconClass: "text-destructive",
      bgClass: "bg-destructive/10",
    },
    {
      label: "Terminé",
      value: stats.done,
      icon: CheckCircle2,
      iconClass: "text-emerald-600",
      bgClass: "bg-emerald-100",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {tiles.map((tile) => (
        <Card key={tile.label} className="print:border print:shadow-none">
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-sm text-muted-foreground">{tile.label}</p>
                <p className="text-2xl font-bold tabular-nums">{tile.value}</p>
              </div>
              <div
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${tile.bgClass}`}
              >
                <tile.icon className={`h-5 w-5 ${tile.iconClass}`} />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
