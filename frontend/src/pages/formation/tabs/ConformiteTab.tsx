import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import HabilitationsTab from "@/pages/formation/tabs/HabilitationsTab";
import ObligationsLegalesTab from "@/pages/formation/tabs/ObligationsLegalesTab";
import type { FormationLegacySub } from "@/pages/formation/formationTabRouting";

type ConformiteSub = "habilitations" | "obligations";

const SUB_FROM_LEGACY: Partial<Record<FormationLegacySub, ConformiteSub>> = {
  habilitations: "habilitations",
  obligations: "obligations",
};

export type ConformiteTabProps = {
  initialSub?: FormationLegacySub;
};

export default function ConformiteTab({ initialSub }: ConformiteTabProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const subParam = searchParams.get("sub") as ConformiteSub | null;

  const resolveInitial = (): ConformiteSub => {
    if (subParam === "habilitations" || subParam === "obligations") return subParam;
    if (initialSub && SUB_FROM_LEGACY[initialSub]) return SUB_FROM_LEGACY[initialSub]!;
    return "habilitations";
  };

  const [sub, setSub] = useState<ConformiteSub>(resolveInitial);

  useEffect(() => {
    setSub(resolveInitial());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSub, subParam]);

  const handleSubChange = (value: string) => {
    const next = value as ConformiteSub;
    setSub(next);
    const params = new URLSearchParams(searchParams);
    params.set("sub", next);
    setSearchParams(params, { replace: true });
  };

  return (
    <Tabs value={sub} onValueChange={handleSubChange}>
      <TabsList className="grid h-11 w-full grid-cols-2 gap-1">
        <TabsTrigger value="habilitations" className="w-full">
          Habilitations
        </TabsTrigger>
        <TabsTrigger value="obligations" className="w-full">
          Obligations légales
        </TabsTrigger>
      </TabsList>
      <TabsContent value="habilitations" className="pt-4">
        <HabilitationsTab defaultAlertFilter hideReferential />
      </TabsContent>
      <TabsContent value="obligations" className="pt-4">
        <ObligationsLegalesTab compactTable />
      </TabsContent>
    </Tabs>
  );
}
