import { Award, Calculator } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type CareerQuickActionsProps = {
  onAugmentationCollective: () => void;
  onNewPromotion: () => void;
};

export function CareerQuickActions({
  onAugmentationCollective,
  onNewPromotion,
}: CareerQuickActionsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Card className="border-primary/20 bg-primary/[0.03]">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Calculator className="h-5 w-5 text-primary" />
            Augmentation collective
          </CardTitle>
          <CardDescription>
            Filtrez une population, simulez l&apos;impact sur la masse salariale, appliquez en lot
            et générez les avenants.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button className="w-full sm:w-auto" onClick={onAugmentationCollective}>
            Ouvrir l&apos;outil
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Award className="h-5 w-5 text-muted-foreground" />
            Promotion individuelle
          </CardTitle>
          <CardDescription>
            Créez un dossier de promotion (poste, salaire, statut, classification) pour un
            collaborateur.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" className="w-full sm:w-auto" onClick={onNewPromotion}>
            Nouvelle promotion
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
