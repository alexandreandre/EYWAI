import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ObjectivesTab from "@/features/formation/components/tabs/ObjectivesTab";
import CompetencesTab from "@/features/formation/components/tabs/CompetencesTab";
import type { FormationLegacySub } from "@/pages/rh/formation/formationTabRouting";

type DeveloppementSub = "objectifs" | "competences";

const SUB_FROM_LEGACY: Partial<Record<FormationLegacySub, DeveloppementSub>> = {
  objectifs: "objectifs",
  competences: "competences",
};

export type DeveloppementTabProps = {
  initialSub?: FormationLegacySub;
};

export default function DeveloppementTab({ initialSub }: DeveloppementTabProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const subParam = searchParams.get("sub") as DeveloppementSub | null;

  const resolveInitial = (): DeveloppementSub => {
    if (subParam === "objectifs" || subParam === "competences") return subParam;
    if (initialSub && SUB_FROM_LEGACY[initialSub]) return SUB_FROM_LEGACY[initialSub]!;
    return "objectifs";
  };

  const [sub, setSub] = useState<DeveloppementSub>(resolveInitial);

  useEffect(() => {
    setSub(resolveInitial());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSub, subParam]);

  const handleSubChange = (value: string) => {
    const next = value as DeveloppementSub;
    setSub(next);
    const params = new URLSearchParams(searchParams);
    params.set("sub", next);
    setSearchParams(params, { replace: true });
  };

  return (
    <Tabs value={sub} onValueChange={handleSubChange}>
      <TabsList className="grid h-11 w-full grid-cols-2 gap-1">
        <TabsTrigger value="objectifs" className="w-full">
          Objectifs
        </TabsTrigger>
        <TabsTrigger value="competences" className="w-full">
          Compétences
        </TabsTrigger>
      </TabsList>
      <TabsContent value="objectifs" className="pt-4">
        <ObjectivesTab simplifiedFilters collapseReportingDefault />
      </TabsContent>
      <TabsContent value="competences" className="pt-4">
        <CompetencesTab defaultSub="gaps" hideReferential collapseMobilityDefault />
      </TabsContent>
    </Tabs>
  );
}
