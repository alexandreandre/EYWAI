import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { SharkFinLoader } from '@/components/SharkFinLoader';

import { getMyOnboarding } from "@/api/onboarding";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

export function FormationOnboardingTabContent({ companyId }: { companyId: string }) {
  const onboardingMe = useQuery({
    queryKey: ["onboarding", "me", companyId],
    queryFn: () => getMyOnboarding(companyId),
    enabled: Boolean(companyId),
    retry: false,
  });

  if (onboardingMe.isPending) {
    return <SharkFinLoader label="Chargement de l'onboarding…" />;
  }

  if (onboardingMe.isError) {
    const st = isAxiosError(onboardingMe.error) ? onboardingMe.error.response?.status : undefined;
    if (st === 404) {
      return (
        <Card>
          <CardHeader>
            <CardTitle>Mon onboarding</CardTitle>
            <CardDescription>Parcours d&apos;intégration</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Votre onboarding n&apos;est pas encore disponible.
            </p>
          </CardContent>
        </Card>
      );
    }
    return (
      <Card>
        <CardHeader>
          <CardTitle>Mon onboarding</CardTitle>
          <CardDescription>Parcours d&apos;intégration</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">
            Impossible de vérifier l&apos;onboarding. Réessayez plus tard.
          </p>
        </CardContent>
      </Card>
    );
  }

  const data = onboardingMe.data!;
  const isComplete = data.progress_pct >= 100;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Mon onboarding</CardTitle>
        <CardDescription>
          {isComplete
            ? "Votre parcours d'intégration est terminé."
            : "Accédez à votre parcours d'intégration et à votre checklist."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Progression</span>
            <span className="font-medium">
              {data.nb_completed}/{data.nb_total} tâches ({Math.round(data.progress_pct)} %)
            </span>
          </div>
          <Progress value={data.progress_pct} className="h-2" />
        </div>
        {isComplete ? (
          <p className="text-sm text-emerald-700 dark:text-emerald-400">
            Félicitations — vous avez complété toutes les étapes de votre intégration.
          </p>
        ) : null}
        <Button asChild variant={isComplete ? "outline" : "default"}>
          <Link to="/employee/onboarding">
            {isComplete ? "Revoir mon onboarding" : "Ouvrir mon onboarding"}
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
