import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import CatalogueTab from "@/pages/formation/tabs/CatalogueTab";
import BudgetTab from "@/pages/formation/tabs/BudgetTab";
import FormationEvaluationsRhSection from "@/pages/formation/FormationEvaluationsRhSection";
import type { FormationLegacySub } from "@/pages/formation/formationTabRouting";

type FormationsSub = "inscriptions" | "catalogue" | "budget";

const SUB_FROM_LEGACY: Partial<Record<FormationLegacySub, FormationsSub>> = {
  catalogue: "catalogue",
  budget: "budget",
  inscriptions: "inscriptions",
};

export type FormationsTabProps = {
  initialSub?: FormationLegacySub;
};

export default function FormationsTab({ initialSub }: FormationsTabProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const subParam = searchParams.get("sub") as FormationsSub | null;

  const resolveInitial = (): FormationsSub => {
    if (subParam === "inscriptions" || subParam === "catalogue" || subParam === "budget") {
      return subParam;
    }
    if (initialSub && SUB_FROM_LEGACY[initialSub]) return SUB_FROM_LEGACY[initialSub]!;
    return "inscriptions";
  };

  const [sub, setSub] = useState<FormationsSub>(resolveInitial);

  useEffect(() => {
    setSub(resolveInitial());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSub, subParam]);

  const handleSubChange = (value: string) => {
    const next = value as FormationsSub;
    setSub(next);
    const params = new URLSearchParams(searchParams);
    params.set("sub", next);
    setSearchParams(params, { replace: true });
  };

  return (
    <div className="space-y-6">
      <Tabs value={sub} onValueChange={handleSubChange}>
        <TabsList className="grid h-11 w-full grid-cols-3 gap-1">
          <TabsTrigger value="inscriptions" className="w-full">
            Inscriptions
          </TabsTrigger>
          <TabsTrigger value="catalogue" className="w-full">
            Catalogue
          </TabsTrigger>
          <TabsTrigger value="budget" className="w-full">
            Budget
          </TabsTrigger>
        </TabsList>
        <TabsContent value="inscriptions" className="pt-4 space-y-6">
          <CatalogueTab forcedMainTab="inscriptions" />
          <FormationEvaluationsRhSection />
        </TabsContent>
        <TabsContent value="catalogue" className="pt-4 space-y-6">
          <CatalogueTab forcedMainTab="catalogue" catalogueTableView />
          <FormationEvaluationsRhSection />
        </TabsContent>
        <TabsContent value="budget" className="pt-4">
          <BudgetTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
