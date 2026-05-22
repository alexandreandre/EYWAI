import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import InterviewTemplatesTab from "@/pages/formation/tabs/InterviewTemplatesTab";
import HabilitationsTab from "@/pages/formation/tabs/HabilitationsTab";
import CompetencesTab from "@/pages/formation/tabs/CompetencesTab";

export type ParametresSubTab = "trames" | "habilitations" | "competences";

const SUB_HINTS: Record<ParametresSubTab, string> = {
  trames: "Modèles d'entretien utilisés dans l'onglet Entretiens.",
  habilitations:
    "Référentiel des types d'habilitation — distinct du suivi des habilitations collaborateurs (Conformité).",
  competences:
    "Référentiel des compétences — distinct de la matrice et des écarts (Développement).",
};

export type ParametresTabProps = {
  initialSub?: ParametresSubTab;
};

export default function ParametresTab({ initialSub = "trames" }: ParametresTabProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const subParam = searchParams.get("sub");

  const resolveInitial = (): ParametresSubTab => {
    if (subParam === "trames" || subParam === "habilitations" || subParam === "competences") {
      return subParam;
    }
    return initialSub;
  };

  const [sub, setSub] = useState<ParametresSubTab>(resolveInitial);

  useEffect(() => {
    setSub(resolveInitial());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSub, subParam]);

  const handleSubChange = (value: string) => {
    const next = value as ParametresSubTab;
    setSub(next);
    const params = new URLSearchParams(searchParams);
    params.set("sub", next);
    setSearchParams(params, { replace: true });
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Référentiels et modèles utilisés dans les entretiens, habilitations et compétences.
      </p>
      <p className="text-xs text-muted-foreground">{SUB_HINTS[sub]}</p>
      <Tabs value={sub} onValueChange={handleSubChange}>
        <TabsList className="grid h-auto min-h-11 w-full grid-cols-1 gap-1 sm:grid-cols-3">
          <TabsTrigger value="trames" className="w-full">
            Trames d&apos;entretien
          </TabsTrigger>
          <TabsTrigger value="habilitations" className="w-full">
            Réf. habilitations
          </TabsTrigger>
          <TabsTrigger value="competences" className="w-full">
            Réf. compétences
          </TabsTrigger>
        </TabsList>
        <TabsContent value="trames" className="pt-4">
          <InterviewTemplatesTab />
        </TabsContent>
        <TabsContent value="habilitations" className="pt-4">
          <HabilitationsTab referentialOnly />
        </TabsContent>
        <TabsContent value="competences" className="pt-4">
          <CompetencesTab referentialOnly />
        </TabsContent>
      </Tabs>
    </div>
  );
}
